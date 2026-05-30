# AOI Field Playbook — imaging, MI/THT, operations

> Provenance: NotebookLM syntheses over 3 research passes (imaging/lighting/optics;
> MI-THT + per-package; AI-AOI operations + failure modes + labeling). Grounded summaries —
> some numeric targets come from specific papers (e.g. YOLO11 benchmarks) and are
> illustrative, not universal. When a figure is paper-specific, treat it as a reference
> point, not a hard spec. Companion to model-selection-per-defect.md, model-defect-matrix.csv,
> and ipc-acceptability-and-taxonomy.md.

---

# PART A — # AOI Imaging & Lighting: Senior Field Reference Guide

## 1. Lighting Geometry: Applications and Defect Coverage

Optical performance in Automated Optical Inspection (AOI) is fundamentally dictated by the interaction between illumination geometry and the topographical features of the PCB. As an architect, you must account for "secondary reflections" from the end faces of electrodes and pads, which act as noise in high-density environments.

| Geometry | Illumination Principle | Surface Visualization | Defect Performance | Physical Constraint Solved |
| :--- | :--- | :--- | :--- | :--- |
| **Coaxial (On-Axis) / Bright-field** | Directed 90° to 45° relative to object via beam splitter. | Highlights planar surfaces and reflective markings. | **Best:** OCR on reflective parts. **Worst:** Solder fillet slope. | Minimizes specular reflection on mirror-like surfaces. |
| **Dome / Shadowless (Diffuse)** | Omnidirectional light "wrapping" around features via hemispherical cavity. | Flattens surface relief; eliminates harsh shadows from tall parts. | **Best:** Presence/absence; OCR on reflective ICs. **Worst:** Solder wetting angle. | Eliminates occlusion shadows in high-density zones. |
| **Dark-field (Low-angle Ring)** | Grazing light (0° to 45° angle) projected off the surface. | Enhances edges, scratches, and height discontinuities. | **Best:** Lifted leads (bright glints); fractures. **Worst:** Planar markings. | Highlights micro-defects via light scattering. |
| **RGB Tri-color (MDMC)** | Multi-tier elevations: Red (Upper), Green (Middle), Blue (Lower). | Converts 3D solder slopes into 2D hue information. | **Best:** Solder wetting angle and fillet shape. **Worst:** Trace shorts. | Solves 360° direction ambiguity (Upward vs. Non-wetted). |

---

## 2. Camera Specifications & Optical Precision

To achieve sub-pixel accuracy for modern SMD packages, hardware must be selected based on Ground Sample Distance (GSD) and optical consistency.

### Resolution and GSD Matrix
Standard AOI resolutions must align with hardware capabilities (e.g., Nordson YESTECH standards). Ultra-small packages like 01005 mandate the high-magnification optical path.

| SMD Package Size | Required Pixel Size (Resolution) | Hardware Requirement |
| :--- | :--- | :--- |
| **Standard (1206, 0805)** | 25 micrometers | 5MP Color Imaging |
| **Small (0603, 0402)** | 12 micrometers | 5MP Color (Standard Mag) |
| **Ultra-Small (0201, 01005)** | 8 micrometers | 5MP Color (**High Mag Option**) |

### Telecentricity and Registration Standards
*   **Telecentric Lenses:** Non-negotiable for measurement accuracy. These optics maintain a constant magnification regardless of component height, ensuring Depth of Field (DoF) consistency and eliminating perspective distortion.
*   **Registration Specifics:** Use a 3-marker fiducial pattern (crosshair or circular). Markers must be **1.0mm in diameter with a 2.0mm clearance** zone. For maximum contrast, use **bare copper on green mask** and ensure all silkscreen legends are removed from the clearance area to prevent registration "false shifts."

---

## 3. Color Discrimination & Material Contrast

RGB-based inspection is superior to grayscale because it utilizes wavelength-specific reflectivity to discriminate materials that share identical grayscale intensities. 

### Material Discrimination via Wavelength

| Material | Primary Wavelength | Optical Characteristic |
| :--- | :--- | :--- |
| **Solder** | Blue (Lower Tier) | Slope & Specular Reflectivity |
| **Copper** | Red (Upper Tier) | Reflectivity & Roughness |
| **Soldermask** | Green (Middle Tier) | Absorption & Texture |
| **Silkscreen** | Full Spectrum (White) | High Diffuse Reflectivity |

### MDMC Differential Image Logic
Standard 360-degree all-around lighting cannot distinguish between "upward wetting" and "non-wetted" conditions because the hue remains identical regardless of direction. Multi-Direction Multi-Color (MDMC) solves this by dividing the illumination into four quadrants (90 degrees apart). By capturing images from the front and back faces of an electrode and generating a **differential intensity image**, the system identifies downward slopes as high-brightness spots, enabling a definitive wetting direction check.

---

## 4. Golden-Sample Reference Methodology

A robust reference set accounts for acceptable process fluctuations while establishing a rigorous baseline.

1.  **Design Data Integration:** Import Gerber (274X/D) and CAD data to define ideal X-Y positioning and polarity.
2.  **Golden Sample Acquisition:** Capture the reference image using **averaged multi-frame acquisition** to neutralize electronic noise and transient artifacts.
3.  **Multi-Sample Set:** Build a set including multiple known-good samples to account for variations in electrode shape, land design, and solder ingredients.
4.  **Lighting Repeatability & Calibration:** 
    *   Maintain uniform brightness at **80-100 lumens/sq inch**.
    *   Verify the **±5 micrometer** positional accuracy target using a **calibration board** with known reference points.
    *   Perform maintenance every **3-6 months or 10,000 inspections**.

---

## 5. Root-Cause Analysis (RCA) of False Calls

Most false calls originate from secondary reflections (ghosting) and occlusion shadows rather than algorithmic failure. To mitigate these, we must pivot from simplistic binary logic to a structured optimization workflow.

### The Optimization Workflow: Clustering to Logical Product
1.  **Clustering:** Use **k-means++** to group measured values of defective shapes (lifting, non-wetting, insufficient solder) into distinct clusters.
2.  **First Logic Identification:** For each cluster, identify the "First Logic"— the specific inspection item that produces the least number of false-positive calls when the entire cluster is flagged.
3.  **Second Logic (Logical Product):** Combine the remaining logics with the First Logic to create a "Logical Product." This minimizes false positives while maintaining a false-negative-free range.

### Senior Engineer Checklist to Fix
1.  **Verify Fiducial Contrast:** Confirm silkscreen is removed around 1.0mm copper markers to ensure **±5 micrometer** registration accuracy.
2.  **Shadow Management:** Deploy **Quad-directional projectors** (Front, Back, Left, Right) to eliminate occlusion shadows from adjacent tall components.
3.  **Address Secondary Reflections:** Inspect for noise generated by end faces of electrodes; adjust MDMC quadrant thresholds to filter these specular artifacts.
4.  **Refine Detection Logic:** Implement the **First Logic/Second Logic** product workflow to replace overly rigid binary thresholds.
5.  **Adjust Criteria Margins:** If a defect is detectable only by a specific logic line, prioritize that line's evaluation value over general thresholds based on actual **process capacity**.

---

# PART B — # MI/THT and Per-Package Defect Inspection Playbook

## 1. THT / Wave / Selective Solder Defect Catalog

The following table serves as the primary technical reference for identifying and remediating soldering discrepancies. As a Senior Process Engineer, your focus must remain on the specific "Process Knobs"—the adjustable parameters that control the thermal and mechanical dynamics of the joint formation.

### Technical Defect Reference

| Defect Type | Visual Signature | Likely Root Cause (Material/PCB) | Likely Root Cause (Process) | Process Knob / Remedy |
| :--- | :--- | :--- | :--- | :--- |
| **Vertical/Barrel Fill %** (Insufficient Hole Fill) | Incomplete solder rise within the Plated Through-Hole (PTH). | Incorrect Pin-to-hole ratio (too tight). | Low solder temperature; excessive fluxer-to-PCB distance; wave height/PCB distance too high. | Increase Solder Pot Temperature; Decrease Fluxer-to-PCB distance; Increase Wave Height. |
| **Hole Fill / Solder Skip** (Insufficient Solder) | Inadequate solder volume; joint fails to meet IPC-A-610 requirements. | Poor solderability of pads/leads; bad flux solids. | Solder dwell time too short; conveyor speed too fast; insufficient flux volume. | Reduce Conveyor Speed; Increase Dipping/Dwell Time; Verify Flux solids concentration. |
| **Icicle / Peak** (Icycling) | Conical or flag-shaped solder extensions from the fillet. | Unusually heat-absorbent surfaces; wrong PTH-to-wire ratio. | Solder solidifying during drainage; inadequate flux; low pot temperature; dross in wave. | Increase Flux volume to promote drainage; Increase Solder Pot Temperature; Remove dross from wave. |
| **Bridging** | Solder extending between adjacent leads, creating a short. | Bent leads; pitch too tight for layout; poor component solderability. | Excess solder; immersion depth too high; contaminated solder; dross in wave; inadequate flux. | Adjust Board Immersion Depth in wave; Perform Solder Pot Analysis; Increase Flux application. |
| **Blow Holes / Pin Holes** | Eruptions, voids, or small holes in the solder fillet. | Moisture in PCB laminate; plating solution in PTH; foreign body in hole. | Inadequate preheat (solvent evaporation failure); water in flux; premature topside PTH freezing. | Increase Bottomside Preheat; Increase Topside Preheat to prevent premature freezing; Replace flux. |
| **Solder Balls** | Tiny spherical shapes dispersed over the PCB surface. | PTH conditions creating pin holes; high ambient humidity. | Insufficient preheat; moisture in the flux. | Increase Preheat Temperature; Control manufacturing floor humidity; Replace water-contaminated flux. |
| **Dewetting** | Solder initially wets the surface, then recedes into droplets. | Surface contamination by abrasives; poor plating or HASL during manufacturing. | N/A | Investigate PCB/Component surface finish; Restore solderability to the base metal. |
| **Non-Wetting** | Solder pulls back, exposing the base metal/pre-soldered surface. | Grease, oil, or dirt; misregistered solder mask; heavily oxidized surfaces. | Low solder temperature; contaminated solder or flux; poor flux application. | Correct Material Discrepancies (Cleaning/Mask alignment); Check Pot Purity; Increase Solder Temp. |
| **Excess Solder** | Bulbous fillet; contours of the lead and land are completely obscured. | Lead length too long; poor solderability of board/component. | Poor drainage; low preheat or solder temperature; incorrect wave exit angle or speed. | Adjust Wave Exit Angle/Speed; Increase Preheat and Solder Pot Temperature; Ensure flux remains. |
| **Dull / Grainy Joints** | Gritty or non-reflective surface on an alloy that is normally bright. | Contaminated solder pot; poor material surface finish. | Joint cooling too slowly or impurity buildup in pot. | Conduct Solder Pot Analysis; Verify against J-STD-006 purity; Check cooling rate. |
| **Flux Residue / White Haze** | White haze on the mask/laminate that cannot be washed off. | Improper curing of solder mask or PCB laminate. | N/A | Bake the PCB to complete the curing cycle of the mask/laminate. |
| **Webbing** | Spider-web-like solder extensions across nonconductive portions. | Improper curing of solder mask/laminate. | Inadequate flux; dross in the solder wave. | Bake the PCB; Increase Flux quantity or substitute with a more viscous flux; Correct drossing. |
| **Lifted Pad** | Pad separates from the PCB laminate. | Poor solderability; material thermal mismatch. | Excessive thermal stress; mechanical vibration before reaching solidus. | Ensure solder reaches solidus temperature immediately after joint formation; Reduce conveyor vibration. |

***

## 2. Per-Package Inspection Playbook

This section maps general defect categories to specific component geometries. Inspectors must prioritize the "Peel-off" movement and thermal mass of these specific packages.

| Package Type | Inspection Focus | Common Defects | Polarity Cue | Criticality / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Electrolytic Capacitor** | Polarity stripe vs. PCB silkscreen; vent condition (bulging/rupture). | Bridging at the base; insufficient hole fill (due to thermal mass). | Polarity stripe (typically negative). | **High Sensitivity:** Inversion or damaged vent requires immediate rejection. |
| **Tantalum Capacitor** | Polarity band orientation; termination wetting. | Non-wetting; Dewetting. | Polarity band (typically positive). | **Note:** Dewetting on terminations is often a sign of contamination by abrasives during lead forming. |
| **DIP IC** | Pin-1 notch orientation; lead coplanarity. | Bridging (bent leads); Icycling; Pin holes. | Pin-1 notch or dot. | **Pass/Fail:** If solder meets J-STD-006 and joints are mechanically sound, do not reject for appearance alone. |
| **THT Resistor** | Body centered between PTH holes; lead protrusion. | Excess solder; Non-wetting. | Color code bands. | Control lead protrusion length to prevent excess solder buildup or accidental bridging. |
| **Multi-pin Connector / Header** | Pin damage/bend; insertion depth; coplanarity. | Solder shorts (especially at end-of-line); Excess solder; Missing pins. | Keying features; Silkscreen. | **Process Note:** Use diagonal exit movement or "Wave Switch Off" at the end of the connector to ensure proper peel-off. |

***

## 3. Inspector's Troubleshooting & Disposition Flowchart

When a defect is identified, follow this hierarchical logic to determine the process remedy and quality disposition.

1.  **Identify Visual Signature and Geometric Category:**
    *   **Bulbous/Obscured:** Excess Solder.
    *   **Spider-web:** Webbing.
    *   **Conical/Flag-shaped:** Icycling.
    *   **Spherical:** Solder Balls.

2.  **Evaluate for Moisture and Thermal Indicators:**
    *   If **Pin holes, Blow holes, or Solder Balls** are detected: The root cause is likely moisture in the laminate or flux.
    *   **Remedy:** Increase Bottomside Preheat and Topside Preheat temperatures. If failure persists, mandate a PCB bake cycle.

3.  **Assess Drainage and Peel-Off Mechanics:**
    *   If **Bridging or Icycling** occurs: The solder is failing to drain (peel-off) from the leads.
    *   **Remedy:** Verify Fluxer-to-PCB distance and flux volume. Check for dross contamination. For connectors, adjust to a diagonal exit angle.

4.  **Quality Disposition (Joint Finish & Purity):**
    *   If joints appear **Dull or Grainy**: Evaluate against **J-STD-006** purity standards.
    *   **DISPOSITION:**
        *   **Accept-As-Is:** If J-STD-006 purity is met and mechanical integrity is verified (joint is not "disturbed").
        *   **Reject and Rework:** If mechanical strength is compromised, the joint is "Cold/Disturbed," or solder impurities exceed allowable limits.

5.  **Thermal/Mechanical Verification:**
    *   For **Cold or Disturbed** joints: Inspect the conveyor for erratic "jerking" or vibration.
    *   **Remedy:** Ensure the joint reaches **Solidus** temperature immediately upon exiting the wave to lock the joint before mechanical vibration occurs.

---

# PART C — # AI-AOI Operations and Reliability Engineering Reference

This reference document establishes the technical specifications and mandatory operational protocols for the deployment and maintenance of YOLO11-based Automatic Optical Inspection (AOI) systems. As Lead Computer Vision Architect, I mandate adherence to these benchmarks to ensure the structural integrity of our Surface Mount Technology (SMT) inspection pipelines.

## 1. OPERATIONAL METRICS & PERFORMANCE BENCHMARKS

Systems must be evaluated against established baselines using high-resolution PCB defect datasets. Performance targets are hardware-dependent and must be validated against the specific deployment environment.

### 1.1 Core Metric Definitions & Targets
Reliability engineering requires the simultaneous optimization of localization precision and classification accuracy. The following metrics are mandated for all system audits:

| Metric | Definition | YOLO11 Target (NVIDIA A100) | YOLO11 Target (Tesla T4) |
| :--- | :--- | :--- | :--- |
| **IoU** | Intersection over Union; measures overlap between predicted ($B_p$) and ground truth ($B_{gt}$) boxes. | Threshold: 0.50 – 0.95 | Threshold: 0.50 – 0.95 |
| **Precision** | Ratio of true positive detections to all predicted positives (Eq. 1). | 94.8% – 99.2% | 94.8% – 99.2% |
| **Recall** | Ratio of true positives to all actual ground truth defects (Eq. 2). | Minimize Escapes | Minimize Escapes |
| **mAP@50-95** | Mean Average Precision across 10 IoU thresholds (0.50 to 0.95). | 0.519 (11n) – 0.551 (11l) | 0.518 (11n) – 0.546 (11l) |

$$Precision = \frac{TP}{TP + FP} \text{ (1)}$$
$$Recall = \frac{TP}{TP + FN} \text{ (2)}$$

### 1.2 Pass/Fail Logic & Throughput Targets
Real-time inspection capability is defined by the average inference time ($t_{inference}$) and frames per second ($FPS$). Engineering teams must verify throughput against the following hardware benchmarks:

*   **Inference Time:** $t_{inference} = T_{total} / N$, where $T_{total}$ is time to process $N$ images. (3)
*   **Throughput:** $FPS = 1 / t_{inference}$. (4)

**Mandatory Throughput Benchmarks (A100):**
*   **YOLO11n (Efficiency Tier):** 166 FPS. Mandatory for high-volume consumer electronics lines.
*   **YOLO11l (Precision Tier):** 32 FPS. Mandatory for high-complexity/high-reliability PCBAs.

### 1.3 Critical Operating Point Analysis
The Precision-Recall (PR) curve illustrates the trade-off between "overkill" (False Positives) and "escapes" (False Negatives). Architects must identify the **"optimal elbow"** of the curve—the point closest to the top-right corner (Precision 1.0, Recall 1.0).
*   **Lowering Confidence Threshold:** Increases Recall (reducing escapes) but sacrifices Precision (increasing overkill).
*   **Raising Confidence Threshold:** Increases Precision (reducing overkill) but risks missing subtle defects (increasing escapes).

### 1.4 Criticality Tuning by Sector
*   **Medical/Automotive (High Criticality):** Engineering teams are mandated to prioritize High Recall and mAP@50-95. The YOLO11l variant must be deployed to ensure maximum localization of coexisting defects.
*   **Consumer Electronics (High Volume):** Teams must prioritize FPS and Precision. The YOLO11n variant is required to maintain real-time throughput without bottlenecking the production line.

---

## 2. AI FAILURE MODES & MITIGATION STRATEGIES

Engineering teams must monitor for specific symptoms of model degradation and apply architectural mitigations provided by the YOLO11 framework.

### 2.1 Environmental Sensitivity
*   **Symptom:** Performance drops due to lighting variations, background noise, or PCB misalignment.
*   **Mitigation:** Deployment of **C2PSA (Channel and Spatial Attention)** and **SPPF (Spatial Pyramid Pooling - Fast)** blocks. These modules consolidate contextual information from multiple receptive fields, focusing the model on defect-relevant regions while suppressing background interference.

### 2.2 Small, Low-Contrast, and Naming Confusion
*   **Symptom:** High misclassification rates for "spur" vs. "spurious copper." Note: Spurious copper precision has been observed as low as 0.727 in certain lightweight variants (YOLO11s).
*   **Mitigation:** Utilize the multi-scale output structure of the Detection Head and the **YOLO Feature Pyramid Network (YFPN)**. This enables hierarchical feature processing, improving the detection of fine-grained defects that are similar in geometry but distinct in classification.

### 2.3 Specular & Geometric Bias
*   **Symptom:** Failure to localize defects accurately in high-resolution images with complex, reflective component geometries.
*   **Mitigation:** Implementation of the **CIoU (Complete Intersection over Union) loss function**. CIoU is mandatory as it incorporates **center-point Euclidean distance** and **aspect ratio consistency**. These geometric constraints counteract reflective bias by forcing the model to optimize for spatial alignment and scale consistency rather than simple overlap.

---

## 3. MONITORING & RE-VALIDATION PROTOCOLS

Post-deployment integrity is non-negotiable. Senior engineers are mandated to perform bi-weekly performance audits.

### 3.1 Continuous Benchmarking
Models must be benchmarked against the original NVIDIA A100 baseline established in Table 2 of the reference. Any deviation exceeding 5% in mAP@50-95 requires immediate pipeline suspension and root cause analysis.

### 3.2 Model Drift & Confusion Matrix Audit
Engineers must use the Confusion Matrix to identify per-class shifts.
*   **Diagonal Concentration:** A "healthy" model must demonstrate high values along the matrix diagonal.
*   **Critical Confusion Pair:** Specifically audit the confusion between **spur** and **spurious copper**.
*   **Background Leakage:** Monitor for "spurious copper" being misclassified as "background" to detect if detection thresholds have drifted too high.

### 3.3 Explainability & Auditability (XAI)
To provide interpretable analysis for AI calls, all systems must implement **Explainable AI (XAI) tools**, such as **Grad-CAM or Heatmaps**. These tools are required to visualize the spatial relationships the model uses to justify a defect call, ensuring auditability during quality failure investigations.

### 3.4 Re-validation Cadence
Model updates must adhere to a strict **70/15/15** (Training/Validation/Testing) data split. This ensures a consistent statistical baseline against the original YOLO11 results.

---

## 4. LABELING & DATASET BEST PRACTICES

Training data quality is the primary determinant of AOI reliability.

### 4.1 Annotation Standards
All defects must be annotated in standard YOLO format: normalized center coordinates ($x, y$), width ($w$), and height ($h$). Bounding boxes must be "meticulous," hugging defect boundaries to support CIoU loss optimization.

### 4.2 Required Sample Counts for Statistical Significance
To reach the reported mAP levels, the dataset must meet the following minimum image counts:

| Defect Class | Original Images | Augmented Images | Total Images |
| :--- | :--- | :--- | :--- |
| Missing Hole | 115 | 115 | 230 |
| Mouse Bite | 115 | 115 | 230 |
| Open Circuit | 116 | 116 | 232 |
| Short Circuit | 116 | 116 | 232 |
| Spur | 115 | 115 | 230 |
| Spurious Copper | 116 | 116 | 232 |
| **TOTAL** | **693** | **693** | **1,386** |

### 4.3 Mandatory Data Augmentation
To improve robustness against orientation shifts, **random rotation augmentation** is mandatory. This process must exactly **double** the dataset size (e.g., adding 693 augmented images to the 693 originals) to ensure the model generalizes to all possible board placements on the conveyor.

### 4.4 Bounding Box Aspect Ratio Consistency
Annotators must maintain center-point placement precision. Inconsistent aspect ratios in labels directly degrade the effectiveness of the CIoU loss function, leading to unstable convergence and poor localization in production.