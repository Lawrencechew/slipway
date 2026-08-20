# PavedPath Architecture (v1)

Mermaid diagrams and high-level description of the architecture.

```mermaid
flowchart TD
  Dev[Developer]
  UI[Frontend]
  API[Backend API]
  DB[(Postgres)]
  Git[GitHub]

  Dev --> UI --> API --> DB
  API --> Git
```
