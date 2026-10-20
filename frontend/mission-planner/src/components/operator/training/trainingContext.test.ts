import { expect, it } from 'vitest';
import { health } from '@/test/operator-fixtures';
import { trainingContext } from './trainingContext';
import type { Mission } from '@/types/mission';
const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const source = {
  ...health,
  source_mode: 'simulation' as const,
  simulation_run_id: namespace,
};
const mission: Mission = {
  id: 'fictional',
  name: 'Training',
  legs: [],
  created_at: '',
  updated_at: '',
  metadata: {
    operator_training_fixture: {
      version: 1,
      namespace,
      prerequisite_record_ids: ['planned'],
    },
  },
};
it('requires simulation, explicit matching fixture metadata and a ready store', () => {
  expect(
    trainingContext(source, mission, 'http://localhost:1234')
  ).toMatchObject({
    identity: {
      storeId: 'store',
      epoch: 'epoch-a',
      missionId: 'fictional',
      fixtureVersion: 1,
    },
    prerequisiteIds: ['planned'],
  });
  for (const h of [
    health,
    { ...source, ready: false },
    { ...source, simulation_run_id: 'ordinary-replay' },
    { ...source, store_id: null },
  ])
    expect(trainingContext(h, mission, 'http://localhost:1234')).toBeNull();
  for (const metadata of [
    {},
    {
      operator_training_fixture: {
        version: 1,
        namespace: 'other',
        prerequisite_record_ids: [],
      },
    },
    {
      operator_training_fixture: {
        version: 2,
        namespace,
        prerequisite_record_ids: [],
      },
    },
    {
      operator_training_fixture: {
        version: 1,
        namespace,
        prerequisite_record_ids: [42],
      },
    },
  ])
    expect(
      trainingContext(source, { ...mission, metadata }, 'http://localhost:1234')
    ).toBeNull();
});
