# ADR 01: Auswahl einer Vektordatenbank

| Status      | Entwurf    |
| ----------- | ---------- |
| Bearbeiter  | SB         |
| Abstimmende | SB, DG     |
| Entwurf     | 09.07.2026 |
| Vorlage     | 09.07.2026 |

## Kontext und Problemstellung

Für RAG-Anwendungen wird eine zentrale Vektordatenbank benötigt. Sie soll semantische und hybride Suche ermöglichen und unabhängig von den konsumierenden Chatbots und MCP-Servern indexiert werden können.

Folgende Kriterien sind relevant:

- Open Source
- Hohe Suchgeschwindigkeit
- Hybrid Search
- LangChain-Integration
- Deployment per Helm auf OpenShift
- Unabhängige Indexierung
- Metadatenfilter
- Backup und Wiederherstellung
- Geringer Betriebsaufwand
- Wiederverwendbarkeit

## Erwägte Möglichkeiten

- Qdrant
- Weaviate
- Milvus
- OpenSearch

## Evaluation

### Qdrant

- Sehr gute LangChain-Integration
- Unterstützt Dense-, Sparse- und Hybrid Search
- Offizielles Helm-Chart
- REST- und gRPC-Schnittstellen für unabhängige Indexierung
- Vergleichsweise geringer Betriebsaufwand
- Bereits in bestehenden Anwendungen im Einsatz

### Weaviate

- Gute Hybrid-Search- und LangChain-Unterstützung
- Offizielles Helm-Chart
- Größerer Funktionsumfang und höherer Betriebsaufwand
- Zusätzliche Anpassungen für OpenShift möglich

### Milvus

- Hohe Skalierbarkeit und Suchleistung
- Gute LangChain- und Hybrid-Search-Unterstützung
- Verteilte Architektur mit mehreren Zusatzkomponenten
- Für den aktuellen Anwendungsfall unnötig komplex

### OpenSearch

- Sehr gute klassische und hybride Suche
- LangChain-Integration und Helm-Chart vorhanden
- Hoher Ressourcen- und Betriebsaufwand
- Funktionsumfang deutlich größer als benötigt

## Übersicht

| Kriterium               | Qdrant | Weaviate | Milvus | OpenSearch |
| ----------------------- | :----: | :------: | :----: | :--------: |
| Open Source             |   +    |    +     |   +    |     +      |
| Hybrid Search           |   +    |    +     |   +    |     +      |
| LangChain-Integration   |   +    |    +     |   +    |     +      |
| OpenShift/Helm          |   +    |    0     |   0    |     0      |
| Unabhängige Indexierung |   +    |    +     |   +    |     +      |
| Betriebsaufwand         |   +    |    0     |   -    |     -      |
| Interne Erfahrung       |   +    |    -     |   -    |     0      |

## Getroffene Entscheidung

Es wird **Qdrant** eingesetzt.

Qdrant erfüllt alle Muss-Kriterien und bietet die beste Kombination aus Hybrid Search, LangChain-Integration, Helm-basierter Bereitstellung und geringem Betriebsaufwand. Zusätzlich besteht bereits interne Erfahrung mit Qdrant, wodurch bestehende Deployment- und Integrationskomponenten wiederverwendet werden können.

Die Indexierung wird als eigenständiger Prozess umgesetzt. MCP-Server und Chatbots greifen über definierte Retrieval-Schnittstellen auf Qdrant zu.
