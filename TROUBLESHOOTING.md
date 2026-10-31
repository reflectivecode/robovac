# RoboVac G32 Pro Troubleshooting Guide

## DPS codes

DPS (Data Point Specification) codes are the numeric identifiers the vacuum
uses over the Tuya local API. The G32 Pro (T2259) uses these, defined in
`custom_components/robovac/vacuums/T2259.py` with defaults in
`custom_components/robovac/vacuums/base.py`:

| DPS | Function                    | Example values                                 |
| --- | --------------------------- | ---------------------------------------------- |
| 2   | Start / pause               |                                                |
| 3   | Direction (manual control)  | `forward`, `back`, `left`, `right`             |
| 5   | Cleaning mode               | `Auto`, `SmallRoom`, `Spot`, `Edge`, `Nosweep` |
| 15  | Status                      | `Running`, `Charging`, `Recharge`, `Sleeping`  |
| 101 | Return home                 |                                                |
| 102 | Fan speed                   | `Standard`, `Turbo`, `Max`, `Boost_IQ`         |
| 103 | Locate                      | `true`, `false`                                |
| 104 | Battery level               | `0`–`100`                                      |
| 106 | Error code                  | `no_error`, `Wheel_stuck`, …                   |
| 107 | Do not disturb              | `true`, `false`                                |
| 109 | Cleaning time (seconds)     |                                                |
| 110 | Cleaning area (m²)          |                                                |
| 135 | Auto return                 | `true`, `false`                                |

## Debug logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.robovac: debug
```

Restart Home Assistant and operate the vacuum. Log entries containing
`Updating entity values from data points: ...` show every DPS code and value
the vacuum reports.

## Common issues

- **Device not responding**: check the IP address (Configure on the
  integration card) and that the access token is current. Eufy rotates local
  keys occasionally; delete and re-add the integration to fetch a new one.
- **Autodiscovery not working**: discovery listens on UDP ports 6666 and 6667,
  which other Tuya integrations (such as localtuya) may already hold. Disable
  autodiscovery and set the IP address manually.
