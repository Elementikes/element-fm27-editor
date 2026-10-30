# Element FM27 Editor v1.0 — Transfer validation

The FM27 player team pointer (`player + 0x130`) and club senior-team chain are mapped in the pinned upstream build. A complete Force Transfer still requires live validation of squad membership and contract/employer linkage before any write is enabled.

## Safety contract

- Never advertise a one-pointer team change as a completed transfer.
- Resolve and validate source team, destination senior team and contract before writing.
- Require read-back after every staged write.
- Roll back/Undo if any validation fails.
- Test risky transfer operations on a backup save first.

## UI milestone

v1.0 introduces a bounded FMRTE-inspired Element player hero with facepack support and fixed-width CA/PA/value/wage metric cards. It also changes the Move to Club warning into an explicit validation gate while the full membership chain is being mapped.
