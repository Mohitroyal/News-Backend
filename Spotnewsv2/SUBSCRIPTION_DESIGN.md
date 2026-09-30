# Spotnewsv2 subscription designs

Editable Figma file: https://www.figma.com/design/GYv2iSRZNOoSYVbJjPmTHy

## Screens

- Choose your plan: https://www.figma.com/design/GYv2iSRZNOoSYVbJjPmTHy?node-id=4-14
- Compare plans: https://www.figma.com/design/GYv2iSRZNOoSYVbJjPmTHy?node-id=4-116
- My subscription: https://www.figma.com/design/GYv2iSRZNOoSYVbJjPmTHy?node-id=4-162

Each screen is 390px wide, with editable text and auto-layout. The file includes reusable button and plan-card components, color and spacing variables, and Inter typography. Compare all features, Back to plans, and Change plan have prototype navigation.

## Draft content

Prices and quotas are proposals, not existing product configuration: Pro INR 299 monthly / INR 2,990 annually; Free 5 and Pro 100 monthly clippings. Benefits require confirmation against the subscription service. Active-subscription usage and dates are sample data. Yearly selection, checkout, contact, cancellation, and billing are visual concepts, not implemented payment flows.

## Source alignment

Uses the Free / Pro / Enterprise plan identifiers from `frountend/src/types/index.ts`, the existing blue/red palette, pale-blue background, and Inter typography used by mobile screens. Implementation should consume the existing subscription service for plan prices, entitlements, checkout, cancellation, and renewal state.

No subscription application code or billing backend was changed.
