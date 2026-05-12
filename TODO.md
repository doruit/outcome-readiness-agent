# TODO

## Backlog

- [ ] **Agentic opportunity identification**  
  Alongside extracting potential outcome-based KPIs from a SoW, add a dedicated analysis step that identifies *agentic opportunities* — specific tasks, workflows, or decision points within the engagement where an autonomous AI agent could replace or augment human effort. Surface these as a structured list (task, current owner, suggested agent pattern) in the card detail and in the agent's JSON response schema.

- [ ] **Broader document input support**  
  Currently the pipeline only accepts Statements of Work. Extend ingestion to handle additional document types such as RFPs, MSAs, project charters, delivery plans, and PowerPoint decks. This requires format-aware pre-processing (e.g. slide extraction, table parsing) before the text is passed to the agents.

- [ ] **Client behaviour assessment**  
  Add an analysis dimension that evaluates the *client side* of the engagement — their organisational readiness, historic delivery track record, decision-making speed, and appetite for risk-sharing. Feed this into the `measurability` and `recommendation` logic so that a technically strong SoW paired with a low-maturity client can be appropriately downgraded.
