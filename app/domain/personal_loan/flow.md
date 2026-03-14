# Personal Loan Flow

```mermaid
flowchart TD
    A[Start Call] --> B[Opening]
    B --> C[Identity Confirmation]
    C --> D[Consent Capture]
    D -->|No| E[End Call: Do Not Contact]
    D -->|Yes| F[Language Selection]
    F --> G[Check Product Interest]
    G -->|Not Interested| H[Close as Not Interested]
    G -->|Interested| I[Collect Employment Type]
    I --> J[Collect Monthly Income]
    J --> K[Collect Loan Amount]
    K --> L[Collect City]
    L --> M[Qualification Rules]
    M -->|Qualified| N[Arrange Human Callback / Next Step]
    M -->|Incomplete| O[Clarify Missing Slots]
    M -->|Not Qualified| P[Polite Close]
    B -->|Busy| Q[Capture Callback Time]
    Q --> R[Schedule Callback]
    B -->|Ask Human| N