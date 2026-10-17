# Data Quality Report

| Check | Rows |
|---|---|
| Raw rows | 20,360 |
| Duplicates removed | 360 |
| Rejected: missing pickup zone | 191 |
| Rejected: invalid status | 0 |
| Rejected: unreadable scheduled time | 0 |
| Rejected: non-positive fare | 108 |
| Rejected: impossible distance | 59 |
| Rejected: drop-off before pick-up | 81 |
| Clean rows | 19,561 |
| Rejected rows | 439 |

**97.8% of unique trips passed every check.** Rejected rows are kept in the `silver_rejected` table with the reason.

# Headline KPIs (Jul–Sep 2026, synthetic data)

- Bookings: 19,561
- Completed trips: 17,571
- Revenue (fares + tips): $1,115,859
- Average on-time pickup rate: 69.2%
- Average cancellation rate: 7.1%
- Average rating: 4.28 / 5
