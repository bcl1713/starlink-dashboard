# Original measurement tables

All values refer to the original application. Cases differ in warm-up, display
mode, client count, history window and instrumentation; read the case metadata
before comparing rows. CPU is consumed cores, memory uses MiB, storage uses KiB.

## CPU and service latency

| Case                     | Measured s | Backend cores | Prom cores | Browser cores | History p50 / p95 / p99 ms (n) | Status observer p50 / p95 / p99 ms (n) |
| ------------------------ | ---------- | ------------- | ---------- | ------------- | ------------------------------ | -------------------------------------- |
| none-r1                  | 120.0      | 0.282         | 0.001      | —             | —                              | 5.4 / 6.5 / 6.8 (25)                   |
| one-r1                   | 120.0      | 0.476         | 0.019      | 9.416         | 192.2 / 285.8 / 398.5 (86)     | 9.8 / 73.3 / 210.0 (25)                |
| one-r2                   | 120.0      | 0.480         | 0.018      | 9.415         | 195.4 / 265.7 / 364.2 (87)     | 10.3 / 100.8 / 107.3 (25)              |
| one-r3                   | 120.0      | 0.472         | 0.019      | 9.414         | 193.4 / 254.6 / 310.2 (86)     | 9.6 / 60.2 / 75.0 (25)                 |
| two-operator-r1          | 120.0      | 0.558         | 0.024      | 9.289         | 213.2 / 387.0 / 485.4 (162)    | 13.1 / 44.3 / 200.2 (25)               |
| two-operator-r2          | 120.0      | 0.560         | 0.023      | 9.291         | 220.0 / 359.3 / 487.0 (163)    | 14.0 / 64.0 / 237.6 (25)               |
| two-operator-r3          | 120.0      | 0.547         | 0.021      | 9.295         | 212.4 / 374.0 / 493.9 (164)    | 15.0 / 202.7 / 250.9 (25)              |
| two-operator-window-300  | 120.0      | 0.477         | 0.023      | 9.388         | 91.7 / 161.4 / 190.6 (189)     | 14.3 / 53.4 / 66.2 (25)                |
| two-operator-window-900  | 120.0      | 0.517         | 0.026      | 9.339         | 141.1 / 203.0 / 248.7 (179)    | 14.9 / 67.6 / 76.2 (25)                |
| activity-control         | 45.0       | 1.397         | 0.024      | 8.423         | 240.8 / 449.2 / 509.7 (62)     | 14.5 / 152.9 / 152.9 (10)              |
| warm-none                | 180.0      | 0.039         | 0.001      | —             | —                              | 5.6 / 6.7 / 7.2 (37)                   |
| warm-one                 | 180.0      | 0.155         | 0.016      | 9.735         | 194.5 / 209.8 / 247.6 (127)    | 9.2 / 76.7 / 201.2 (37)                |
| warm-two-operator        | 180.0      | 0.227         | 0.019      | 9.626         | 230.5 / 362.6 / 394.8 (240)    | 12.4 / 175.4 / 213.8 (37)              |
| two-operator-window-3600 | 120.0      | 0.532         | 0.013      | 9.304         | 198.3 / 361.6 / 437.3 (166)    | 14.7 / 205.2 / 219.5 (25)              |
| counters-warm-two-r1     | 180.0      | 0.247         | 0.020      | 9.603         | 217.2 / 342.5 / 385.4 (242)    | 10.5 / 183.8 / 200.1 (37)              |
| counters-warm-two-r2     | 180.0      | 0.246         | 0.020      | 9.611         | 219.9 / 355.4 / 392.2 (245)    | 12.7 / 167.8 / 258.7 (37)              |
| operator-only            | 120.0      | 0.281         | 0.001      | 0.021         | —                              | 5.7 / 6.6 / 7.2 (25)                   |

## Memory and measured slopes

| Case              | Memory owner    | Last MiB | Max MiB | OLS MiB/min | n   | Span s |
| ----------------- | --------------- | -------- | ------- | ----------- | --- | ------ |
| warm-none         | Backend         | 330.80   | 331.20  | 0.04        | 37  | 180.0  |
| warm-none         | Prometheus      | 27.34    | 31.35   | 0.93        | 37  | 180.0  |
| warm-one          | Backend         | 329.60   | 332.51  | -1.04       | 37  | 180.0  |
| warm-one          | Prometheus      | 41.62    | 45.41   | 3.13        | 37  | 180.0  |
| warm-one          | Browser PSS     | 1175.30  | 1205.08 | 27.85       | 37  | 180.0  |
| warm-one          | Browser JS heap | 53.78    | 118.44  | -7.25       | 37  | 180.0  |
| warm-two-operator | Backend         | 341.62   | 341.62  | 0.49        | 37  | 180.0  |
| warm-two-operator | Prometheus      | 38.44    | 45.40   | 2.49        | 37  | 180.0  |
| warm-two-operator | Browser PSS     | 2182.86  | 2195.24 | 80.70       | 37  | 180.0  |
| warm-two-operator | Browser JS heap | 143.38   | 185.35  | -6.93       | 37  | 180.0  |
| operator-only     | Backend         | 334.95   | 463.15  | -34.02      | 25  | 120.0  |
| operator-only     | Prometheus      | 27.81    | 29.95   | -0.05       | 25  | 120.0  |
| operator-only     | Browser PSS     | 252.72   | 252.72  | 1.20        | 25  | 120.0  |
| operator-only     | Browser JS heap | 10.29    | 10.43   | 0.40        | 25  | 120.0  |
| activity-control  | Backend         | 453.27   | 897.73  | -19.91      | 10  | 45.0   |
| activity-control  | Prometheus      | 31.13    | 33.96   | 1.38        | 10  | 45.0   |
| activity-control  | Browser PSS     | 1911.65  | 1911.65 | 177.68      | 10  | 45.0   |
| activity-control  | Browser JS heap | 157.62   | 184.38  | 20.53       | 10  | 45.0   |

## Persistent storage and measured slopes

| Case              | Storage owner                | Last KiB | OLS KiB/min | n   | Span s |
| ----------------- | ---------------------------- | -------- | ----------- | --- | ------ |
| warm-none         | SQLite DB                    | 1944.00  | 0.00        | 6   | 170.0  |
| warm-none         | SQLite WAL                   | 0.00     | 0.00        | 6   | 170.0  |
| warm-none         | Application data (inclusive) | 2017.37  | 0.00        | 6   | 170.0  |
| warm-none         | Routes/cache/export          | 2.28     | 0.00        | 6   | 170.0  |
| warm-none         | Prometheus WAL               | 353.00   | 71.98       | 6   | 170.0  |
| warm-none         | Prometheus blocks            | 229.18   | 0.00        | 6   | 170.0  |
| warm-none         | Prometheus head chunks       | 128.00   | 51.61       | 6   | 170.0  |
| warm-one          | SQLite DB                    | 1944.00  | 0.00        | 6   | 160.0  |
| warm-one          | SQLite WAL                   | 0.00     | 0.00        | 6   | 160.0  |
| warm-one          | Application data (inclusive) | 2017.37  | 0.00        | 6   | 160.0  |
| warm-one          | Routes/cache/export          | 2.28     | 0.00        | 6   | 160.0  |
| warm-one          | Prometheus WAL               | 335.56   | 73.46       | 6   | 160.0  |
| warm-one          | Prometheus blocks            | 229.69   | 0.00        | 6   | 160.0  |
| warm-one          | Prometheus head chunks       | 128.00   | 55.46       | 6   | 160.0  |
| warm-two-operator | SQLite DB                    | 1944.00  | 0.00        | 6   | 160.0  |
| warm-two-operator | SQLite WAL                   | 0.00     | 0.00        | 6   | 160.0  |
| warm-two-operator | Application data (inclusive) | 2017.37  | 0.00        | 6   | 160.0  |
| warm-two-operator | Routes/cache/export          | 2.28     | 0.00        | 6   | 160.0  |
| warm-two-operator | Prometheus WAL               | 331.25   | 72.00       | 6   | 160.0  |
| warm-two-operator | Prometheus blocks            | 229.64   | 0.00        | 6   | 160.0  |
| warm-two-operator | Prometheus head chunks       | 128.00   | 53.51       | 6   | 160.0  |
| activity-control  | SQLite DB                    | 1628.00  | —           | 1   | 0.0    |
| activity-control  | SQLite WAL                   | 0.00     | —           | 1   | 0.0    |
| activity-control  | Application data (inclusive) | 1707.64  | —           | 1   | 0.0    |
| activity-control  | Routes/cache/export          | 2.28     | —           | 1   | 0.0    |
| activity-control  | Prometheus WAL               | 28.07    | —           | 1   | 0.0    |
| activity-control  | Prometheus blocks            | 227.07   | —           | 1   | 0.0    |
| activity-control  | Prometheus head chunks       | 0.00     | —           | 1   | 0.0    |

## Repeated original controls

Repeated startup/preparation controls (three original runs each; same windowed
workload and harness):

| Controls                                          | Metric         | Min     | Median  | Max     |
| ------------------------------------------------- | -------------- | ------- | ------- | ------- |
| one-r1, one-r2, one-r3                            | Backend cores  | 0.472   | 0.476   | 0.480   |
| one-r1, one-r2, one-r3                            | History p95 ms | 254.584 | 265.668 | 285.753 |
| two-operator-r1, two-operator-r2, two-operator-r3 | Backend cores  | 0.547   | 0.558   | 0.560   |
| two-operator-r1, two-operator-r2, two-operator-r3 | History p95 ms | 359.306 | 374.017 | 386.956 |

These ranges measure run-to-run variability, not uncertainty bounds or
application gains.
