# Concept Flow — Outcome Readiness Review

```mermaid
flowchart LR
    A[Scan docs van bestaande engagement] --> B[Extract outcomes en KPI's]
    B --> B1[Identificeer potentiële revenue uplift]
    B --> B2[Identificeer Agentic kansen]
    B --> B3[Identificeer gaps, risico's, kansen en klant gedrag]
    B1 & B2 & B3 --> D[Human-in-the-loop review]
    D --> E[Valideer, corrigeer en prioriteer]
    E --> F[Prepare briefing voor EM]
    F --> G[Genereer concrete instructies en next steps]
    G --> H[Send instructions]

    A:::step
    B:::step
    B1:::revenue
    B2:::agentic
    B3:::step
    D:::human
    E:::human
    F:::step
    G:::step
    H:::step

    classDef step    fill:#EAF3FF,stroke:#0078D4,color:#0F172A,stroke-width:1px;
    classDef human   fill:#FFF4E5,stroke:#F59E0B,color:#0F172A,stroke-width:1px;
    classDef revenue fill:#ECFDF5,stroke:#10B981,color:#0F172A,stroke-width:1px;
    classDef agentic fill:#F5F3FF,stroke:#7C3AED,color:#0F172A,stroke-width:1px;
```

## Stappen

| Stap | Beschrijving |
|---|---|
| **Scan docs** | Bestaande engagement-documenten (SoW, RFP, MSA, etc.) worden ingelezen. |
| **Extract outcomes en KPI's** | Meetbare business outcomes en KPI's worden automatisch geïdentificeerd. |
| **Potentiële revenue uplift** 🟢 | De financiële waarde van omzetting naar outcome-based pricing wordt geschat. |
| **Agentic kansen** 🟣 | Taken en beslismomenten die door een AI-agent overgenomen kunnen worden, worden in kaart gebracht. |
| **Gaps, risico's en kansen** 🔵 | Ontbrekende KPI's, onduidelijke scope, commerciële risico's én klant gedrag (organisatorische volwassenheid, besluitvaardigheid en risicobereidheid) worden zichtbaar gemaakt. |
| **Human-in-the-loop review** | Een reviewer controleert en verrijkt de geëxtraheerde inzichten. |
| **Valideer, corrigeer en prioriteer** | De reviewer stelt de prioritering bij en keurt de bevindingen goed. |
| **Prepare briefing voor EM** | De uitkomst wordt samengevat in een briefing voor de Engagement Manager. |
| **Genereer instructies** | Concrete acties en next steps worden voorbereid. |
| **Send instructions** | Briefing en instructies worden doorgestuurd naar de betrokken partijen. |
