#!/usr/bin/env python3
"""
Configure dashboard clocks based on environment variables.

This script reads TIMEZONE_TAKEOFF and TIMEZONE_LANDING from .env
and regenerates the dashboard JSON files with the configured timezones.

Usage:
    python3 configure_clocks.py
"""

import json
import os
from pathlib import Path


def load_env_file():
    """Load environment variables from .env file"""
    env_vars = {}
    env_file = Path('.env')

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()

    return env_vars


# Load environment variables from .env
env_vars = load_env_file()

# Get timezone configuration (fallback to defaults if not in .env)
TIMEZONE_TAKEOFF = env_vars.get('TIMEZONE_TAKEOFF', os.getenv('TIMEZONE_TAKEOFF', 'America/Los_Angeles'))
TIMEZONE_LANDING = env_vars.get('TIMEZONE_LANDING', os.getenv('TIMEZONE_LANDING', 'Europe/London'))

print(f"Configuring clocks with timezones:")
print(f"  TIMEZONE_TAKEOFF: {TIMEZONE_TAKEOFF}")
print(f"  TIMEZONE_LANDING: {TIMEZONE_LANDING}")

def get_timezone_display(timezone):
    """Get display name and offset for timezone"""
    tz_map = {
        "UTC": ("Zulu / UTC", "UTC+0"),
        "America/Los_Angeles": ("Los Angeles", "PST/PDT"),
        "America/New_York": ("Washington DC", "EDT/EST"),
        "America/Chicago": ("Chicago", "CDT/CST"),
        "America/Denver": ("Denver", "MDT/MST"),
        "Europe/London": ("London", "BST/GMT"),
        "Europe/Paris": ("Paris", "CEST/CET"),
        "Europe/Amsterdam": ("Amsterdam", "CEST/CET"),
        "Asia/Tokyo": ("Tokyo", "JST"),
        "Asia/Shanghai": ("Shanghai", "CST"),
        "Asia/Hong_Kong": ("Hong Kong", "HKT"),
        "Australia/Sydney": ("Sydney", "AEDT/AEST"),
    }
    return tz_map.get(timezone, (timezone, timezone))


def create_text_clock_panel(title, emoji, timezone, x, y, panel_id):
    """Create a text panel with large, legible time display"""
    tz_display = get_timezone_display(timezone)

    return {
        "type": "text",
        "title": f"{emoji} {tz_display[0]}",
        "gridPos": {
            "h": 4,
            "w": 6,
            "x": x,
            "y": y
        },
        "id": panel_id,
        "options": {
            "content": f"""<div style="display: flex; flex-direction: column; justify-content: center; align-items: center; width: 100%; height: 100%; font-family: 'Courier New', monospace; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 10px; box-sizing: border-box; overflow: hidden;">
  <div id="clock" style="font-size: 48px; font-weight: bold; color: #00ff00; text-shadow: 0 0 10px rgba(0,255,0,0.5); letter-spacing: 2px; font-family: 'Courier New', monospace; line-height: 1.2;">00:00:00</div>
  <div style="font-size: 12px; color: #90EE90; margin-top: 8px; font-weight: 500; white-space: nowrap;">{tz_display[0]}</div>
  <div style="font-size: 10px; color: #B0E0E6; margin-top: 2px; white-space: nowrap;">{tz_display[1]}</div>
</div>
<script>
(function() {{
  const clockDiv = document.getElementById('clock');
  function updateClock() {{
    try {{
      const now = new Date();
      const formatter = new Intl.DateTimeFormat('en-US', {{
        timeZone: '{timezone}',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }});
      const timeStr = formatter.format(now);
      if (clockDiv) {{
        clockDiv.textContent = timeStr;
      }}
    }} catch(e) {{
      console.error('Clock error:', e);
    }}
  }}
  // Initial update
  updateClock();
  // Update every 500ms for better performance
  setInterval(updateClock, 500);
}})();
</script>""",
            "mode": "html"
        },
        "fieldConfig": {
            "defaults": {},
            "overrides": []
        }
    }


def configure_dashboard(filename, custom_timezones=None):
    """Update dashboard with configured clocks"""
    print(f"\n=== {filename} ===")

    filepath = Path(f'monitoring/grafana/provisioning/dashboards/{filename}')

    with open(filepath) as f:
        dashboard = json.load(f)

    panels = dashboard['panels']

    # Default clock configuration: UTC, Takeoff, Landing, Tokyo
    # Override with custom_timezones if provided
    if custom_timezones is None:
        custom_timezones = [
            ("UTC", 0),
            (TIMEZONE_TAKEOFF, 6),
            (TIMEZONE_LANDING, 12),
            ("Asia/Tokyo", 18)
        ]

    clock_configs = [
        ("🌍", custom_timezones[0][0], custom_timezones[0][1]),
        ("🗽", custom_timezones[1][0], custom_timezones[1][1]),
        ("🇬🇧", custom_timezones[2][0], custom_timezones[2][1]),
        ("🗾", custom_timezones[3][0], custom_timezones[3][1]),
    ]

    new_panels = []
    replaced_count = 0
    panel_id = 300

    for panel in panels:
        if panel.get('type') == 'text' and any(x in panel.get('title', '') for x in ['🌍', '🗽', '🇬🇧', '🗾']):
            # Replace this text-based clock panel
            replaced_count += 1
            gridpos = panel['gridPos']
            emoji, timezone, x = clock_configs[replaced_count - 1]
            new_clock = create_text_clock_panel(
                "Clock",
                emoji,
                timezone,
                x,
                gridpos['y'],
                panel_id
            )
            new_panels.append(new_clock)
            panel_id += 1
            tz_display = get_timezone_display(timezone)
            print(f"✅ {emoji} {tz_display[0]} ({timezone})")
        else:
            new_panels.append(panel)

    dashboard['panels'] = new_panels
    dashboard['version'] = dashboard.get('version', 1) + 1

    with open(filepath, 'w') as f:
        json.dump(dashboard, f, indent=2)

    print(f"   Version: {dashboard['version']}")
    return replaced_count


def main():
    """Configure all dashboards"""
    print("Configuring Starlink Dashboard Clocks\n")
    print("=" * 70)

    total_clocks = 0
    for filename in ['overview.json', 'network-metrics.json', 'position-movement.json']:
        count = configure_dashboard(filename)
        total_clocks += count

    print("\n" + "=" * 70)
    print(f"✅ Configured {total_clocks} clock panels across all dashboards")
    print(f"\nClock Configuration:")
    print(f"  🌍 UTC (Zulu)")
    print(f"  🗽 {get_timezone_display(TIMEZONE_TAKEOFF)[0]} ({TIMEZONE_TAKEOFF})")
    print(f"  🇬🇧 {get_timezone_display(TIMEZONE_LANDING)[0]} ({TIMEZONE_LANDING})")
    print(f"  🗾 Tokyo (Asia/Tokyo)")
    print(f"\nTo change timezones, edit .env and run this script again:")
    print(f"  python3 configure_clocks.py")


if __name__ == '__main__':
    main()
