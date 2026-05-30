# IPC Acceptability and Defect-Judgment Reference for AI Visual Inspection

## 1. ACCEPTABILITY CLASSES AND SECTOR APPLICATION

The categorization of electronic assemblies into three distinct classes—as defined by IPC-A-610 and J-STD-001—dictates the required sensitivity and precision of Automated Optical Inspection (AOI) algorithms. In an AI-augmented Quality Management System (QMS), detection thresholds must be calibrated to the specific reliability requirements of the end-use environment described in the source documentation.

| IPC Class | Reliability Requirement | Primary Sector Application | AI Decision Logic (Process vs. Defect) |
| :--- | :--- | :--- | :--- |
| **Class 1** | **General Electronic Products** | Consumer toys, basic peripherals | Focus on core functionality; cosmetic variances are acceptable. |
| **Class 2** | **Dedicated Service** | **Mobile Phones / Consumer Electronics** | Continuous performance required; minor placement offsets are classified as Process Indicators unless they impact long-term stability. |
| **Class 3** | **High Performance/Harsh Environment** | **Medical Electronics / Life-support Systems** | Uninterrupted performance is mandatory. **Downtime is not tolerated.** Any condition posing a "Safety Hazard" is a Defect. |

### The "Same Visual Condition" Logic and Class 3 Mandates
A condition identified by AI feature extraction may be judged differently based on the assembly's class. For instance, a "tiny crack" or "component mismatch" that satisfies Class 2 tolerances might be labeled a Process Indicator. However, for **Class 3 Medical Electronics**, such conditions are mandated as **Defects**. These subtle anomalies represent "Safety Hazards" and "performance instability" (Source 1) that could lead to catastrophic failure in life-critical systems. Therefore, Class 3 deployments require a prioritized Recall focus over raw Precision to eliminate latent failures.

---

## 2. QUANTITATIVE DEFECT ACCEPT/REJECT CRITERIA

This reference establishes the engineering benchmarks for AI-driven inspection. To ensure compliance with high-reliability standards, systems must meet or exceed the following quantitative metrics derived from current research in Deep Learning (DL) architectures.

### AI Inspection Thresholds by Defect Type

| Defect Category | Standard Reference | Visual Signature (DL Feature Map) | AI Detection Benchmark |
| :--- | :--- | :--- | :--- |
| **Through-hole/Via** | IPC-A-610 | Via fill failures; Missing holes | **95.4% mAP** [PKU-Market-PCB] |
| **Solder Joint Quality** | J-STD-001 | Cold joints, Bridging, Insufficient solder | **84.0% AP** [Pad-Specific Metrics] |
| **Component Placement** | IPC-A-610 | Missing components, Misalignment, Mismatches | **99.1% Precision** (Capacitors); **89.3% Precision** (Resistors) |
| **PCB Trace/Circuitry** | IPC-A-610 | Open/Short circuits, Mouse bites, Spurs, Spurious copper | **94.6% Precision** [General PCB Trace] |

### Advanced Model Performance Standards
*   **High-Precision Benchmark (Class 3):** For critical medical assemblies, the **ResNet50 + t-SNE + K-means** hybrid architecture—which achieved a **97.33% accuracy rate** (Source 5)—is the mandated baseline for high-precision defect recognition.
*   **Fine Segmentation Standard:** For precise dimensional measurement of solder joint morphology, systems must adhere to the **Y-MaskNet** benchmark of **0.72 mAP@[0.5:0.95]** (Source 4), ensuring superior pixel-level localization over standard YOLOv5 or Mask R-CNN baselines.

---

## 3. THE THREE-BUCKET CLASSIFICATION: DEFECT VS. PROCESS-INDICATOR VS. ACCEPTABLE

To maintain high throughput on SMT lines while minimizing false alarms that plague classical rule-based AOI, the Liaison mandates the following "Three-Bucket" logic based on Learned Feature Hierarchies.

1.  **Acceptable (Golden Reference):**
    *   **Technical Definition:** Images representing the "Golden Reference" templates.
    *   **Visual Examples:** Uniform solder fillets and centered components as observed in the *pcb_wacv_2019* dataset.
2.  **Process-Indicator:**
    *   **Technical Definition:** Features that do not affect "stability" or "lifespan" but indicate process drift.
    *   **AI Context:** Minor visual anomalies caused by "lighting variation" or "placement tolerance" that DL models generalize better than legacy systems (Source 3).
3.  **Defect (Reject):**
    *   **Technical Definition:** Conditions that "degrade performance" or "lead to safety hazards."
    *   **Visual Examples:** True Positives found in *PKU-Market-PCB* and *DeepPCB* datasets, such as missing holes or copper spurs.

---

## 4. DEFECT TAXONOMY AND PROCESS ROOT CAUSE ANALYSIS

AI detection results must be integrated into the corrective action loop. The following diagnostic guide links visual signatures to manufacturing "Process Knobs."

*   **Solder Bridges / Shorts**
    *   **Visual Signature:** Conductive material connecting two or more pads/traces.
    *   **Likely Root Cause:** Solder paste formulation issues or improper stencil thickness.
    *   **Process Knob:** Adjust **Reflow temperature zones** or paste stencil aperture.
*   **Misaligned / Missing Components**
    *   **Visual Signature:** Component absent from pad or rotated outside IPC bounds.
    *   **Likely Root Cause:** Systematic offsets in the Pick-and-Place machine.
    *   **Process Knob:** Recalibrate X-Y coordinates or inspect **feeder vacuum pressure**.
*   **Insufficient Solder / Cold Joints**
    *   **Visual Signature:** Incomplete wetting or dull surface (often confused with metal reflections).
    *   **Likely Root Cause:** Wave/Reflow thermal mass issues.
    *   **Process Knob:** Increase pre-heat temperature or refine lighting for feature extraction.
*   **Trace Defects (Spurs / Mouse Bites)**
    *   **Visual Signature:** Narrowing of trace (mouse bite) or excess copper (spur).
    *   **Likely Root Cause:** PCB bare board fabrication errors (etching/lamination).
    *   **Process Knob:** Audit chemical etching at the fabrication level.

---

## 5. DPMO AND PARETO BENCHMARKS (IPC-7912)

Managing SMT lines running at "thousands of components per minute" requires a statistically rigorous Pareto analysis framework. The following benchmarks are specified for AI-augmented IPC-7912 reporting.

### High-Frequency Defect Pareto
1.  **Resistors:** Identified as a primary Pareto item due to **89.3% precision**; resistors are susceptible to misidentification in dense layouts where morphological similarity to pads is high.
2.  **LED Lights:** Challenging in complex backgrounds (standard mAP ~77.8%).
3.  **Capacitors:** High stability detection (99.1% Precision) due to distinct geometry.
4.  **Pads:** Frequent site for soldering defects.
5.  **Traces:** Location of open/short circuit risks.

### DPMO Calculation and Throughput Requirements
*   **100-ms Inspection Window:** To meet the cadence of modern SMT lines, model inference—including pre- and post-processing—is mandated to occur within a **100-ms window** (Source 3).
*   **Modern Industrial Requirement:** Systems must target a minimum of **93.1% Precision** and **84.6% Recall** (Improved YOLOv11) to ensure DPMO calculations accurately reflect real-world quality without manual re-review floods.

---

## 6. AI INSPECTION DEPLOYMENT & QUALITY AUDIT TRAIL

To maintain compliance within ISO 27001 and enterprise Quality Management Systems, the following technical requirements are specified for the AOI deployment.

### Model Traceability and Explainability
*   **Grad-CAM Mandatory:** Rejection decisions must be traceable via **Grad-CAM (Gradient-weighted Class Activation Mapping)**. This visualization allows quality architects to audit pixel-level features that triggered a "Defect" label, ensuring model explainability.

### Data Security and Residency
*   **ISO 27001 Compliance:** Since board images represent sensitive intellectual property, systems must implement:
    *   **VPC Isolation:** For image storage data lakes (e.g., Amazon S3).
    *   **Encryption:** Mandated at rest and in transit using AWS KMS or Azure Key Vault.
    *   **IAM Roles:** Strict Identity and Access Management for audit logs and model artifacts.

### Continuous Drift Management
*   **Quality Degradation Prevention:** Board revisions change over time. Quality architects must deploy **MLflow** or **SageMaker Model Monitor** to detect feature drift. Automated alerts are mandated to trigger whenever model performance deviates from the established precision/recall baseline.