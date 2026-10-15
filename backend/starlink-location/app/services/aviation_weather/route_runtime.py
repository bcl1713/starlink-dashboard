"""Demand-owned route geometry joined to current UTC and persistent notices."""

import asyncio
from collections import OrderedDict

from app.mission.storage import get_active_leg_lock
from app.models.route_sigmets import (
    RouteSigmetEntry,
    RouteSigmetSnapshot,
    SelectedSigmetEntry,
    UnresolvedFeature,
)
from app.services.overview_weather.protocol import WeatherUnavailable

from .decode import await_owned
from .relations import cancellation_matches
from .route_decode import GeometryWorker
from .route_identity import digest, group_bulletins
from .route_state import NoticeConflict


class RouteSigmetService:
    def __init__(self, weather, store, context_provider):
        self.weather, self.store = weather, store
        self.context_provider = context_provider
        self.worker = GeometryWorker()
        self._cache = OrderedDict()
        self._evaluations = {}
        self._selected_context_key = None
        self._closed = False
        self._closing = None
        self.weather.add_settings_listener(self.settings_changed)

    async def settings_changed(self, settings):
        if not settings.sigmet:
            await self._stop_evaluations()
            self._cache.clear()

    async def _stop_evaluations(self):
        tasks = list(self._evaluations)
        for task in tasks:
            task.cancel()
        await await_owned(
            asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
        )

    @staticmethod
    async def _thread(operation):
        owned = asyncio.create_task(asyncio.to_thread(operation))
        try:
            return await asyncio.shield(owned)
        finally:
            await await_owned(owned)

    def _select_context(self):
        with get_active_leg_lock().acquire(timeout=1):
            return self._observe_context()

    def _observe_context(self):
        """Called under the active-leg gate; publish the latest selection key.

        Admission checks the key again after thread/cleanup awaits, so an older
        capture cannot retire a more recently observed route's work.
        """
        context = self.context_provider()
        self._selected_context_key = context.context_key if context else None
        return context

    async def _retire_incompatible(self, context):
        key = context.context_key if context else None
        if key != self._selected_context_key:
            raise WeatherUnavailable()
        tasks = [task for task, owner in self._evaluations.items() if owner != key]
        for task in tasks:
            task.cancel()
        await await_owned(
            asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
        )
        if key != self._selected_context_key:
            raise WeatherUnavailable()

    async def _selection(self):
        context = await self._thread(self._select_context)
        await self._retire_incompatible(context)
        return context

    def _settings(self):
        return self.weather.store.get(timeout=1)

    async def _geometry(self, context, collection, groups):
        current = await self._selection()
        _, admitted = self.weather.admitted_layer("sigmet")
        if (
            self._closed
            or admitted is not collection
            or current is None
            or current.context_key != context.context_key
            or context.context_key != self._selected_context_key
        ):
            raise WeatherUnavailable()
        # Canonical semantic content ignores acquisition metadata, ring/feature
        # order and whitespace. Eligibility and acknowledgement stay outside the
        # geometry cache. Feature IDs bind cached spans to this exact payload.
        content = digest(
            [(g.bulletin_key, g.semantic_digest, g.feature_ids) for g in groups]
        )
        key = (context.context_key, content)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        task = asyncio.create_task(self.worker.evaluate(context, collection))
        self._evaluations[task] = context.context_key
        try:
            result = await task
        finally:
            self._evaluations.pop(task, None)
            await await_owned(
                asyncio.ensure_future(asyncio.gather(task, return_exceptions=True))
            )
        self._cache[key] = result
        self._cache.move_to_end(key)
        while len(self._cache) > 2:
            self._cache.popitem(last=False)
        return result

    @staticmethod
    def _eligible(groups, now):
        cancellations = [
            g.properties
            for g in groups
            if g.properties.get("cancelled")
            and g.valid_from_ms <= now < g.expires_at_ms
        ]
        return [
            g
            for g in groups
            if not g.properties.get("cancelled")
            and g.valid_from_ms
            <= now
            < min(g.properties["valid_to_ms"], g.expires_at_ms)
            and not any(cancellation_matches(g.properties, c) for c in cancellations)
        ]

    def _validate(
        self, context, product, groups, keys, selected, settings, eligibility
    ):
        # Called under the notice file lock: pure current in-memory checks only.
        now = self.weather.utc_ms()
        current, collection = self.weather.admitted_layer("sigmet", now)
        if (
            self._closed
            or not settings.sigmet
            or selected is None
            or selected.context_key != context.context_key
            or collection is None
            or current.instance_id != product.instance_id
            or current.state not in {"ready", "stale"}
            or {g.notice_key(context.context_key) for g in self._eligible(groups, now)}
            != eligibility
            or not keys.issubset(eligibility)
        ):
            raise NoticeConflict("Route SIGMET notice is no longer current")

    async def _operation(
        self, context, product, groups, keys, operation, *, eligibility=None
    ):
        if eligibility is None:
            eligibility = {
                g.notice_key(context.context_key)
                for g in self._eligible(groups, self.weather.utc_ms())
            }

        def execute():
            # Entire bounded lock/I/O operation runs off-loop. Route selection
            # and settings reads happen BEFORE taking the notice file lock.
            with get_active_leg_lock().acquire(timeout=1):
                selected = self._observe_context()
                settings = self._settings()

                def validate():
                    self._validate(
                        context, product, groups, keys, selected, settings, eligibility
                    )

                validate()
                return operation(validate, self.weather.utc_ms())

        return await self._thread(execute)

    def _snapshot(
        self,
        settings,
        context,
        product,
        status,
        *,
        entries=None,
        selected_entries=None,
        unresolved=None,
        future=None,
        omitted=0,
        state_revision=0,
        reason=None
    ):
        entries, unresolved = entries or [], unresolved or []
        complete = status in {"ready", "stale"} and not unresolved and not omitted
        return RouteSigmetSnapshot(
            schema="route-sigmets-v1",
            generated_at_ms=self.weather.utc_ms(),
            settings_revision=settings.revision,
            state_revision=state_revision,
            generation_id=digest(
                [
                    context.context_key if context else None,
                    settings.revision,
                    product.instance_id,
                    [(e.notice_key, e.semantic_digest) for e in entries],
                ]
            ),
            context=context,
            sigmet_product=product,
            status=status,
            reason=reason,
            complete=complete,
            truncated=False,
            entries=entries,
            selected_entries=selected_entries or [],
            unresolved=unresolved,
            future_feature_ids=future or [],
            omitted_features=omitted,
        )

    async def read(self):
        snapshot, _ = await self._read()
        return snapshot

    def _capture(self):
        with get_active_leg_lock().acquire(timeout=1):
            return (
                self._observe_context(),
                self._settings(),
                self.weather.admitted_layer("sigmet")[0],
            )

    async def _changed_snapshot(self, reason, status="evaluating"):
        current, settings, product = await self._thread(self._capture)
        await self._retire_incompatible(current)
        if not settings.sigmet:
            status = "off"
        elif current is None:
            status = "no-route"
        return self._snapshot(settings, current, product, status, reason=reason), None

    async def _read(self):
        settings = await self._thread(self._settings)
        await self.weather.settings_changed(settings)
        product, _ = self.weather.admitted_layer("sigmet")
        if self._closed:
            raise WeatherUnavailable()
        if not settings.sigmet:
            return self._snapshot(settings, None, product, "off"), None
        context = await self._selection()
        product, collection = await self.weather.read_layer("sigmet")
        current, current_settings, current_product = await self._thread(self._capture)
        await self._retire_incompatible(current)
        if (
            not current_settings.sigmet
            or (current.context_key if current else None)
            != (context.context_key if context else None)
            or current_product.instance_id != product.instance_id
        ):
            return await self._changed_snapshot("Route or SIGMET input changed")
        context, settings, product = current, current_settings, current_product
        if context is None:
            return (
                self._snapshot(
                    settings, None, product, "no-route", reason="Route unavailable"
                ),
                None,
            )
        if collection is None:
            return (
                self._snapshot(
                    settings,
                    context,
                    product,
                    "unavailable",
                    reason="SIGMET source unavailable",
                ),
                None,
            )
        groups = await self._thread(lambda: group_bulletins(collection["features"]))
        try:
            geometry = await self._geometry(context, collection, groups)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            return await self._changed_snapshot("Matching superseded")
        except WeatherUnavailable:
            return await self._changed_snapshot("Matching unavailable", "unavailable")
        now = self.weather.utc_ms()
        eligible = self._eligible(groups, now)
        eligibility = {g.notice_key(context.context_key) for g in eligible}
        matches = {m.feature_id: m.spans for m in geometry.matches}
        matched = [g for g in eligible if any(f in matches for f in g.feature_ids)]
        keys = {g.notice_key(context.context_key) for g in matched}
        try:
            state = await self._operation(
                context,
                product,
                groups,
                keys,
                lambda validate, instant: self.store.reconcile_sync(
                    context.context_key, matched, instant, validate=validate,
                    selection_eligible=eligible,
                ),
                eligibility=eligibility,
            )
        except NoticeConflict:
            return await self._changed_snapshot("Route or SIGMET input changed")
        entries = []
        for group in matched:
            record = state.records[group.notice_key(context.context_key)]
            spans = [span for f in group.feature_ids for span in matches.get(f, [])]
            spans.sort(
                key=lambda s: (s.segment_index, s.start_fraction, s.end_fraction)
            )
            entries.append(
                RouteSigmetEntry(
                    notice_key=group.notice_key(context.context_key),
                    bulletin_key=group.bulletin_key,
                    semantic_digest=group.semantic_digest,
                    feature_ids=group.feature_ids,
                    spans=spans,
                    attention_order=record.attention_order,
                    acknowledged=record.acknowledged,
                    selected=record.selected,
                    valid_from_ms=group.valid_from_ms,
                    expires_at_ms=group.expires_at_ms,
                    identity_uncertain=group.identity_uncertain,
                )
            )
        entries.sort(
            key=lambda e: (
                e.spans[0].segment_index,
                e.spans[0].start_fraction,
                e.notice_key,
            )
        )
        matched_keys = {group.notice_key(context.context_key) for group in matched}
        selected_entries = []
        for group in eligible:
            key = group.notice_key(context.context_key)
            record = state.records.get(key)
            if key in matched_keys or record is None or not record.selected or record.acknowledged:
                continue
            selected_entries.append(SelectedSigmetEntry(
                notice_key=key, bulletin_key=group.bulletin_key,
                semantic_digest=group.semantic_digest, feature_ids=group.feature_ids,
                attention_order=record.attention_order, acknowledged=False, selected=True,
                valid_from_ms=group.valid_from_ms, expires_at_ms=group.expires_at_ms,
                identity_uncertain=group.identity_uncertain,
            ))
        eligible_ids = {f for g in eligible for f in g.feature_ids}
        unresolved = {
            u.feature_id: u for u in geometry.unresolved if u.feature_id in eligible_ids
        }
        for group in eligible:
            if group.identity_uncertain:
                for feature in group.feature_ids:
                    unresolved.setdefault(
                        feature,
                        UnresolvedFeature(
                            feature_id=feature, reason="identity-uncertain"
                        ),
                    )
        omitted = collection.get("omitted_features", 0)
        incomplete = bool(
            unresolved
            or omitted
            or not geometry.complete
            or collection.get("feed_completeness") != "complete"
        )
        current_product, _ = self.weather.admitted_layer("sigmet")
        if current_product.instance_id != product.instance_id:
            return await self._changed_snapshot("SIGMET input changed")
        product = current_product
        status = (
            "incomplete"
            if incomplete
            else ("stale" if product.state == "stale" else "ready")
        )
        snapshot = self._snapshot(
            settings,
            context,
            product,
            status,
            entries=entries,
            selected_entries=selected_entries,
            unresolved=list(unresolved.values()),
            omitted=omitted,
            state_revision=state.state_revision,
            future=sorted(
                f
                for g in groups
                if not g.properties.get("cancelled") and now < g.valid_from_ms
                for f in g.feature_ids
            ),
            reason="Coverage or route intersection unknown" if incomplete else None,
        )
        try:
            # Recheck after assembling the bounded response, including a new
            # validity start that would otherwise publish an obsolete empty set.
            await self._operation(
                context,
                product,
                groups,
                keys,
                lambda validate, instant: validate(),
                eligibility=eligibility,
            )
        except NoticeConflict:
            return await self._changed_snapshot("Route or SIGMET input changed")
        return snapshot, (context, product, groups)

    async def select(self, change):
        snapshot, binding = await self._read()
        if binding is None or snapshot.context.context_key != change.context_key:
            raise NoticeConflict('SIGMET route is no longer current')
        context, product, groups = binding
        group = next((group for group in self._eligible(groups, self.weather.utc_ms())
                      if group.bulletin_key == change.bulletin_key
                      and group.semantic_digest == change.semantic_digest), None)
        if group is None:
            raise NoticeConflict('SIGMET report is no longer current')
        await self._operation(
            context, product, groups, {group.notice_key(context.context_key)},
            lambda validate, instant: self.store.select_sync(change, group, instant, validate=validate),
        )
        result = await self.read()
        if result.context is None or result.context.context_key != change.context_key:
            raise NoticeConflict('SIGMET route changed while selecting')
        return result

    async def acknowledge(self, change):
        snapshot, binding = await self._read()
        if (
            binding is None
            or snapshot.context.context_key != change.context_key
            or not any(
                e.notice_key == change.notice_key
                and e.semantic_digest == change.semantic_digest
                for e in [*snapshot.entries, *snapshot.selected_entries]
            )
        ):
            raise NoticeConflict("Route SIGMET notice is no longer current")
        context, product, groups = binding
        keys = {change.notice_key}
        confirmation = await self._operation(
            context,
            product,
            groups,
            keys,
            lambda validate, instant: self.store.set_ack_sync(
                change, instant, validate=validate
            ),
        )
        await self._operation(
            context, product, groups, keys, lambda validate, instant: validate()
        )
        return confirmation

    async def _close(self):
        self._closed = True
        self.weather.remove_settings_listener(self.settings_changed)
        await self._stop_evaluations()
        await self.worker.aclose()
        self._cache.clear()

    async def aclose(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._close())
        await await_owned(self._closing)
