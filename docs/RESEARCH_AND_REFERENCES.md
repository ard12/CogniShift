# RESEARCH & REFERENCES
## Statutory Standards, Engineering Codes, and Peer-Reviewed Scientific Foundations
*Smart India Hackathon 2026 | Team 087 (Den of Devs) | Problem Statement: SIH26117*

---

### 1. Overview & Engineering Principles
In safety-critical industrial environments, software systems must be grounded in established engineering standards, cybersecurity frameworks, and peer-reviewed artificial intelligence research. CogniShift uses selected engineering standards as constraints and reference inputs for deterministic verification workflows. This document details the statutory, regulatory, and academic foundations that inform our system architecture.

---

### 2. Statutory Industrial Engineering Standards
CogniShift references established engineering standards to guide its deterministic validation workflows:

#### A. ASME Boiler and Pressure Vessel Code (BPVC) Section VIII, Divisions 1 & 2 (ASME, 2023)
The ASME Section VIII standard governs the design, fabrication, and inspection of pressure vessels in oil and gas refineries. CogniShift embeds standard statutory formulas into its deterministic execution sandbox. For example, the minimum required wall thickness of a thin-walled cylindrical pressure vessel under internal design pressure is evaluated strictly by:

$$t = (P * R) / (S * E - 0.6 * P) + C$$

Where:
- $t$ = Minimum required shell thickness (inches or mm)
- $P$ = Internal design pressure (psi or MPa)
- $R$ = Inside radius of the vessel shell (inches or mm)
- $S$ = Maximum allowable stress value of material (psi or MPa)
- $E$ = Joint efficiency factor (e.g., 1.0 for 100% radiographed welds, 0.85 for spot examined)
- $C$ = Corrosion allowance specified for process fluid (inches or mm)

By synthesizing and executing Python code that implements this formula rather than asking an AI model to perform mental arithmetic, CogniShift eliminates floating-point errors and validates calculations against defined engineering constraints deterministically.

#### B. OSHA 1910.119: Process Safety Management (PSM) of Highly Hazardous Chemicals
The United States Occupational Safety and Health Administration (OSHA) sets guidelines to prevent catastrophic releases of hazardous chemicals. CogniShift aligns its operational design with key PSM principles:
- **Process Safety Information (PSI):** Maintains verified, searchable digital records of relief system parameters, piping specifications, and design limits.
- **Standard Operating Procedures (SOPs):** Provides operators with clear, grounded operating limits and structured shutdown sequences.
- **Management of Change (MOC):** Ensures any proposed alteration to operating parameters requires documented technical review and authorization.

#### C. OISD-118: Safety and Fire Protection Layout in Hydrocarbon Processing Plants
Published by India's Oil Industry Safety Directorate (Ministry of Petroleum and Natural Gas), OISD guidance informs refinery safety and auditability considerations used in the design, including fail-safe equipment interlocks and structured operating logs.

---

### 3. Industrial Cybersecurity & Air-Gap Regulations
#### A. IEC 62443 / ISA-99: Industrial Automation & Control Systems Security
IEC 62443 defines security levels and network segmentation for industrial environments according to the Purdue Model:
- **Purdue Level 0/1:** Physical equipment, sensors, actuators, and basic process transmitters.
- **Purdue Level 2:** Control systems, Distributed Control Systems (DCS), and Programmable Logic Controllers (PLCs).
- **Purdue Level 3:** Operations management, plant historians, and operator control consoles.
- **Purdue Level 3.5 DMZ:** Demilitarized security buffer preventing direct traffic between plant operations and corporate enterprise networks.

CogniShift is engineered for deployment in Purdue Level 3 or 3.5. It adheres to IEC 62443 zone and conduit segmentation principles by eliminating external gateway conduits and maintaining a zero public-cloud egress posture during operation.

#### B. NIST Special Publication 800-82 Rev. 2: Guide to ICS Security
Published by NIST, this guide provides recommendations for securing Industrial Control Systems. CogniShift follows NIST recommendations by providing local audit logging, role-based access control, and operational independence from external cloud services.

#### C. Digital Personal Data Protection (DPDP) Act 2023 (Government of India)
Local processing reduces exposure associated with sending sensitive information to external services and supports DPDP-aligned data governance. By keeping sensitive processing, documents, and logs within on-premise infrastructure, cross-border transmission risks are eliminated.

---

### 4. Academic & AI Safety Foundations
#### A. RAGAS Framework for RAG Assessment (Es et al., 2024)
Published at EACL 2024 (*"RAGAS: Automated Evaluation of Retrieval Augmented Generation"*), this framework establishes methodology for evaluating grounded retrieval:
- **Faithfulness:** The proportion of claims in the generated answer that can be directly inferred from the retrieved context.
- **Context Precision:** The signal-to-noise ratio of retrieved chunks relative to the user query.

RAGAS motivates evaluation of faithfulness and context precision; CogniShift separately uses a configured retrieval threshold as an implementation safeguard to filter weak evidence and reduce unsupported responses. If retrieved manual chunks fall below this threshold, the system explicitly alerts the operator that supporting documentation is unavailable rather than generating an ungrounded response.

#### B. Cryptographic Authorization (W3C WebCrypto & FIPS 186-4)
For human authorization, CogniShift implements the W3C Web Cryptography API utilizing ECDSA on the NIST P-256 curve. ECDSA provides cryptographic proof of key possession; one-time challenges, TTLs, server-side session controls, and nonce handling provide replay resistance.

---
*CONFIDENTIAL & SOVEREIGN  |  SOVEREIGN ON-PREMISE SYSTEM — ZERO PUBLIC-CLOUD EGRESS DURING OPERATION*
