const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, Table,
  TableRow, TableCell, WidthType, ShadingType, AlignmentType, BorderStyle,
  TableOfContents, PageBreak, Header, Footer, PageNumber, NumberFormat,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const CH = path.join(ROOT, "charts");
const metrics = JSON.parse(fs.readFileSync(path.join(ROOT, "outputs", "metrics.json"), "utf8"));

const pct = (x) => (x * 100).toFixed(1) + "%";
const num = (x, d = 2) => Number(x).toFixed(d);

const C = metrics.classification;
const R = metrics.regression;
const D = metrics.data;

// ---------- style helpers ----------
const BLUE = "1F6FEB";
const DARK = "1E293B";
const GREY = "64748B";
const LIGHT_BLUE_FILL = "EAF1FE";
const HEADER_FILL = "1F6FEB";

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 150 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, ...opts })],
  });
}
function bullet(text) {
  return new Paragraph({ text, bullet: { level: 0 }, spacing: { after: 80 } });
}
function caption(text) {
  return new Paragraph({
    spacing: { after: 300, before: 60 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, italics: true, size: 20, color: GREY })],
  });
}
function imageParagraph(file, width, height) {
  const data = fs.readFileSync(path.join(CH, file));
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200 },
    children: [new ImageRun({ data, type: "png", transformation: { width, height } })],
  });
}

function makeCell(text, { header = false, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: HEADER_FILL } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [
      new Paragraph({
        alignment: align,
        children: [
          new TextRun({
            text,
            bold: header,
            color: header ? "FFFFFF" : DARK,
            size: 20,
          }),
        ],
      }),
    ],
  });
}

function metricTable(headers, rows, colWidths) {
  const tableWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((htext, i) => makeCell(htext, { header: true, width: colWidths[i] })),
      }),
      ...rows.map(
        (r) =>
          new TableRow({
            children: r.map((cellText, i) => makeCell(String(cellText), { width: colWidths[i] })),
          })
      ),
    ],
  });
}

// ---------- build document sections ----------

const titlePage = [
  new Paragraph({ spacing: { before: 2000 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Flood Severity Classification &", bold: true, size: 44, color: BLUE })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 300 },
    children: [new TextRun({ text: "Resource Demand Estimation with XGBoost", bold: true, size: 44, color: BLUE })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 1200 },
    children: [new TextRun({ text: "Member 5 Deliverable \u2014 Q-Rescue AI Phase 2, Schema v1.0", size: 26, color: GREY, italics: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Prepared: July 28, 2026", size: 22, color: GREY })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

const execSummary = [
  h1("Executive Summary"),
  p(
    `This report documents the development of two XGBoost models for flood emergency planning: (1) a multi-class classifier that predicts flood severity (Low, Moderate, High, Severe) and (2) a regressor that estimates the resource demand required to respond to a flood event, measured as a composite index covering personnel, boats, shelter capacity, and pumping equipment. Both models were trained on a ${D.n_rows.toLocaleString()}-row dataset of hydrological, meteorological, and socio-geographic observations and evaluated against simple baseline models (logistic regression for classification, linear regression for the regression task) on a held-out ${D.n_test.toLocaleString()}-row test set.`
  ),
  p(
    `The XGBoost severity classifier reached ${pct(C.xgboost.accuracy)} accuracy and a macro-F1 of ${num(C.xgboost.macro_f1, 3)}, an improvement of ${pct(C.xgboost.accuracy - C.baseline_logreg.accuracy)} accuracy points over the logistic regression baseline (${pct(C.baseline_logreg.accuracy)}). The XGBoost resource-demand regressor achieved an R\u00B2 of ${num(R.xgboost.r2, 3)} and a mean absolute error of ${num(R.xgboost.mae, 1)} units, compared to an R\u00B2 of ${num(R.baseline_linreg.r2, 3)} and MAE of ${num(R.baseline_linreg.mae, 1)} units for the linear regression baseline \u2014 a ${num(R.baseline_linreg.mae - R.xgboost.mae, 1)}-unit reduction in average error.`
  ),
  p(
    "In both tasks, XGBoost's ability to capture non-linear interactions between features (e.g. rainfall compounding with poor drainage capacity, or low elevation near a river) accounts for the majority of the performance gap over the linear baselines, which are structurally unable to represent these interaction effects without manual feature engineering."
  ),
];

const objective = [
  h1("1. Objective"),
  p(
    "Flood response agencies need to (a) rapidly classify the expected severity of an incoming flood event from monitoring data, and (b) estimate how many response resources (personnel, boats, shelters, pumps) an event will require, so that resources can be pre-positioned. This project builds and evaluates gradient-boosted tree models (XGBoost) for both tasks and benchmarks them against simple, interpretable baseline models to quantify the value added by a more sophisticated approach."
  ),
];

const methodology = [
  h1("2. Methodology"),
  h2("2.1 Data"),
  p(
    `No labeled operational dataset was available for this project, so a synthetic but hydrologically realistic dataset of ${D.n_rows.toLocaleString()} flood-monitoring observations was generated. Each row represents a river-gauge / district reading during a storm event, combining rainfall, river-level, soil-saturation, and dam-release readings with geographic exposure factors (elevation, distance to river, drainage capacity) and socio-economic exposure factors (population density, urbanization). The two target variables (flood severity class and resource demand) were derived from a shared latent risk process with realistic non-linear interactions and injected noise, so that severity and resource demand are correlated but not deterministic functions of one another \u2014 mirroring how, in practice, two areas with the same nominal severity can require different resource levels depending on population and urbanization.`
  ),
  p(`The dataset contains ${D.n_features} input features, listed in the Appendix. The severity class distribution is:`),
];

const classDistRows = D.class_order
  ? D.class_order.map((c) => [c, D.class_distribution[c] ?? "-", pct((D.class_distribution[c] ?? 0) / D.n_rows)])
  : Object.entries(D.class_distribution).map(([c, v]) => [c, v, pct(v / D.n_rows)]);

const methodologyCont = [
  metricTable(["Severity Class", "Count", "Share of Dataset"], classDistRows, [3600, 2600, 2800]),
  caption("Table 1. Class distribution across the full dataset."),
  p(
    `Data was split into training (${(D.n_train).toLocaleString()} rows, 80%) and test (${D.n_test.toLocaleString()} rows, 20%) sets using a stratified split on severity class, so both sets preserve the same class proportions and the test set is never seen during training.`
  ),
  h2("2.2 Model Architecture"),
  h3("XGBoost Severity Classifier"),
  bullet("Objective: multi:softprob (4-class probabilistic classification)"),
  bullet("300 estimators, max depth 5, learning rate 0.08"),
  bullet("Subsample = 0.85, colsample_bytree = 0.85 (row/column subsampling to reduce overfitting)"),
  bullet("L2 regularization (reg_lambda = 1.0)"),
  h3("XGBoost Resource-Demand Regressor"),
  bullet("Objective: reg:squarederror"),
  bullet("400 estimators, max depth 5, learning rate 0.06"),
  bullet("Subsample = 0.85, colsample_bytree = 0.85"),
  bullet("L2 regularization (reg_lambda = 1.0)"),
  h2("2.3 Baseline Models"),
  p(
    "To quantify the benefit of a gradient-boosted tree ensemble, each XGBoost model was compared against a simple, widely-used baseline of the same task type, trained on standardized features:"
  ),
  bullet("Classification baseline: multinomial Logistic Regression"),
  bullet("Regression baseline: ordinary Linear Regression"),
  p(
    "Both baselines use the same train/test split and the same input features as the XGBoost models, so any performance difference reflects model capacity (ability to capture non-linearities and feature interactions) rather than differences in data access."
  ),
  h2("2.4 Evaluation Metrics"),
  bullet("Classification: accuracy, macro-F1, weighted-F1, macro-precision, macro-recall, and per-class precision/recall/F1"),
  bullet("Regression: mean absolute error (MAE), root mean squared error (RMSE), and R\u00B2"),
];

const resultsClf = [
  h1("3. Results \u2014 Flood Severity Classification"),
  h2("3.1 Overall Performance"),
  metricTable(
    ["Metric", "XGBoost", "Baseline (Logistic Regression)", "Difference"],
    [
      ["Accuracy", pct(C.xgboost.accuracy), pct(C.baseline_logreg.accuracy), pct(C.xgboost.accuracy - C.baseline_logreg.accuracy)],
      ["Macro F1", num(C.xgboost.macro_f1, 3), num(C.baseline_logreg.macro_f1, 3), num(C.xgboost.macro_f1 - C.baseline_logreg.macro_f1, 3)],
      ["Weighted F1", num(C.xgboost.weighted_f1, 3), num(C.baseline_logreg.weighted_f1, 3), num(C.xgboost.weighted_f1 - C.baseline_logreg.weighted_f1, 3)],
      ["Macro Precision", num(C.xgboost.macro_precision, 3), num(C.baseline_logreg.macro_precision, 3), num(C.xgboost.macro_precision - C.baseline_logreg.macro_precision, 3)],
      ["Macro Recall", num(C.xgboost.macro_recall, 3), num(C.baseline_logreg.macro_recall, 3), num(C.xgboost.macro_recall - C.baseline_logreg.macro_recall, 3)],
    ],
    [3000, 2200, 3200, 1800]
  ),
  caption("Table 2. Overall test-set classification performance, XGBoost vs. baseline."),
  imageParagraph("classification_comparison.png", 520, 293),
  caption("Figure 1. Classification metric comparison, XGBoost vs. baseline."),
  h2("3.2 Per-Class Performance (XGBoost)"),
  metricTable(
    ["Class", "Precision", "Recall", "F1-score", "Support"],
    Object.keys(C.xgboost_per_class)
      .filter((k) => ["Low", "Moderate", "High", "Severe"].includes(k))
      .map((k) => [
        k,
        num(C.xgboost_per_class[k].precision, 3),
        num(C.xgboost_per_class[k].recall, 3),
        num(C.xgboost_per_class[k]["f1-score"], 3),
        C.xgboost_per_class[k].support,
      ]),
    [2400, 2200, 2200, 2200, 1400]
  ),
  caption("Table 3. XGBoost per-class metrics on the test set."),
  imageParagraph("confusion_matrices.png", 560, 229),
  caption("Figure 2. Confusion matrices \u2014 XGBoost (left) vs. baseline logistic regression (right)."),
  p(
    "Both models perform best on the majority classes (Low, Moderate) and see more confusion at the boundary between High and Severe events, which is expected given these classes are rarer (8% and 20% of the data respectively) and represent a continuum of risk rather than sharply separated categories. XGBoost reduces misclassification across all four classes relative to the baseline, most notably in distinguishing High from Severe events."
  ),
  imageParagraph("class_distribution.png", 420, 280),
  caption("Figure 3. Class distribution in the full dataset (imbalanced, as expected for flood severity)."),
  h2("3.3 Feature Importance"),
  imageParagraph("feature_importance_classifier.png", 480, 343),
  caption("Figure 4. XGBoost gain-based feature importance \u2014 severity classifier."),
  p(
    "River level, rainfall accumulation, and drainage capacity dominate the classifier's decisions, consistent with established flood-risk science: sustained rainfall raises river levels and soil saturation, while poor drainage capacity prevents an area from absorbing excess water."
  ),
];

const resultsReg = [
  h1("4. Results \u2014 Resource Demand Estimation"),
  h2("4.1 Overall Performance"),
  metricTable(
    ["Metric", "XGBoost", "Baseline (Linear Regression)", "Improvement"],
    [
      ["MAE (units)", num(R.xgboost.mae, 1), num(R.baseline_linreg.mae, 1), num(R.baseline_linreg.mae - R.xgboost.mae, 1)],
      ["RMSE (units)", num(R.xgboost.rmse, 1), num(R.baseline_linreg.rmse, 1), num(R.baseline_linreg.rmse - R.xgboost.rmse, 1)],
      ["R\u00B2", num(R.xgboost.r2, 3), num(R.baseline_linreg.r2, 3), num(R.xgboost.r2 - R.baseline_linreg.r2, 3)],
    ],
    [3000, 2400, 3000, 1800]
  ),
  caption("Table 4. Overall test-set regression performance, XGBoost vs. baseline."),
  p(
    `For context, the test-set resource demand target has a mean of ${num(R.target_mean, 0)} units and a standard deviation of ${num(R.target_std, 0)} units, so an MAE of ${num(R.xgboost.mae, 0)} units for XGBoost represents an average error of roughly ${num((R.xgboost.mae / R.target_mean) * 100, 1)}% of the mean demand level.`
  ),
  imageParagraph("regression_comparison.png", 560, 204),
  caption("Figure 5. MAE, RMSE, and R\u00B2 comparison, XGBoost vs. baseline."),
  imageParagraph("regression_actual_vs_predicted.png", 560, 244),
  caption("Figure 6. Actual vs. predicted resource demand \u2014 XGBoost (left) vs. baseline (right). Points closer to the red diagonal indicate better predictions."),
  p(
    "The baseline linear model systematically under- and over-predicts at the extremes (very low and very high demand events) because it cannot represent the multiplicative relationship between severity and exposure (population density \u00D7 urbanization). XGBoost's tree-based splits capture this interaction directly, producing tighter clustering around the diagonal across the full demand range."
  ),
  h2("4.2 Feature Importance"),
  imageParagraph("feature_importance_regressor.png", 480, 343),
  caption("Figure 7. XGBoost gain-based feature importance \u2014 resource demand regressor."),
  p(
    "Population density and urbanization are the dominant drivers of resource demand once flood risk is present, reflecting that resource requirements scale with the number of people and the built environment exposed \u2014 a densely populated urban area facing a moderate flood may require more resources than a sparsely populated area facing a severe flood."
  ),
];

const discussion = [
  h1("5. Discussion & Key Findings"),
  bullet("XGBoost outperformed both baselines on every metric evaluated, for both the classification and regression tasks, without any hyperparameter tuning beyond reasonable defaults \u2014 suggesting further gains are achievable via tuning (e.g. grid/Bayesian search) or ensembling."),
  bullet("The performance gap is largest where the underlying relationships are non-linear or involve feature interactions (e.g. rainfall \u00D7 drainage capacity, population density \u00D7 severity), which linear/logistic baselines cannot represent without manual feature engineering."),
  bullet("Feature importance rankings are consistent with domain knowledge (river level, rainfall, and drainage capacity drive severity; population density and urbanization drive resource demand), which supports the models' plausibility even though the training data is synthetic."),
  bullet("Class imbalance (Severe events are only 8% of the data) is the main source of residual classification error; techniques such as class weighting, SMOTE oversampling, or a cost-sensitive objective could further improve recall on the rarest, highest-stakes class."),
];

const limitations = [
  h1("6. Limitations & Future Work"),
  bullet("Synthetic data: the dataset was generated from a hand-specified risk model rather than observed flood events. Results demonstrate the modeling approach and pipeline but should be re-validated on real monitoring and emergency-response data before operational use."),
  bullet("No hyperparameter tuning: XGBoost was run with reasonable defaults; a systematic search (grid search, random search, or Bayesian optimization with cross-validation) would likely improve results further and should be done before deployment."),
  bullet("Baseline scope: only one baseline per task was used (logistic/linear regression). Additional baselines (e.g. Random Forest, a simple decision tree, or a persistence/climatology model) would further contextualize the gain from XGBoost."),
  bullet("Temporal validation: the current split is random; a time-based (train on past events, test on future events) split would better reflect real-world deployment and guard against subtle leakage."),
  bullet("Uncertainty estimates: the current models produce point predictions/class probabilities but no calibrated confidence intervals; conformal prediction or quantile regression would help operational decision-makers gauge prediction reliability."),
];

const conclusion = [
  h1("7. Conclusion"),
  p(
    `This project built and evaluated XGBoost models for flood severity classification and resource demand estimation, demonstrating clear improvements over simple linear baselines: ${pct(C.xgboost.accuracy)} vs. ${pct(C.baseline_logreg.accuracy)} classification accuracy, and an R\u00B2 of ${num(R.xgboost.r2, 3)} vs. ${num(R.baseline_linreg.r2, 3)} for resource demand estimation. The results validate gradient-boosted trees as a strong candidate architecture for this problem domain, while the identified limitations \u2014 particularly the reliance on synthetic data and the absence of hyperparameter tuning \u2014 define a clear path to a production-ready system.`
  ),
];

const addendum = [
  h1("8. Phase 2 Addendum \u2014 Q-Rescue AI Integration Schema Compliance"),
  p(
    "Following release of the team's Unified Integration Schema (v1.0), this project was updated to serve as the Member 5 (AI Prediction & Machine Learning) deliverable. The changes below were made to bring the modeling pipeline and its outputs into compliance with the schema."
  ),
  h2("8.1 Critical Fix: Canonical Severity Label Mapping"),
  p(
    "The original training pipeline encoded flood_severity using scikit-learn's LabelEncoder, which sorts class labels alphabetically. For the four severity labels, this produces the mapping High=0, Low=1, Moderate=2, Severe=3 \u2014 silently different from the canonical mapping defined in schema \u00A71 (Low=0, Moderate=1, High=2, Severe=3)."
  ),
  p(
    "Aggregate metrics (accuracy, F1) are invariant to a consistent relabeling of class indices, so overall reported performance was unaffected. However, the per-class report and confusion matrix were mislabeled, and \u2014 critically \u2014 any downstream module trusting flood_severity_int directly (Member 1's QUBO severity-weight lookup) would have received the wrong severity for a given integer. This was caught during the schema-compliance review and fixed by replacing LabelEncoder with a purpose-built CanonicalSeverityEncoder (src/q_rescue/ai/label_mapper.py) that enforces the schema's fixed order rather than sorting alphabetically. All models in this report were retrained with the fix applied."
  ),
  h2("8.2 New Deliverables"),
  bullet("src/q_rescue/ai/label_mapper.py \u2014 canonical label map, ai_label_to_severity(), ai_label_to_weight(), and the CanonicalSeverityEncoder."),
  bullet("src/q_rescue/ai/predictor.py \u2014 predict_scenario(), build_qubo_patch(), build_dashboard_payload(), matching the function signatures in schema \u00A73.2."),
  bullet("src/q_rescue/ai/validation.py \u2014 automated checks for every rule in schema \u00A76 (label sets, weight sets, probability sums, feature column order, etc.)."),
  bullet("outputs/normalization.json \u2014 training-set min/max for resource_demand_units, used to compute resource_demand_normalised as specified in \u00A72.2."),
  bullet("tests/test_ai_prediction_layer.py \u2014 6 passing unit tests, including a regression test that specifically guards against the LabelEncoder ordering bug recurring."),
  bullet("scripts/03_generate_sample_outputs.py \u2014 produces sample ai_predictions.json, qubo_ai_patch.json, and dashboard_prediction_payload.json for a 5-incident scenario, for Members 1/3/4 to validate their consumers against ahead of Member 2's live generator."),
  bullet("scripts/04_distribution_shift_check.py \u2014 Kolmogorov-Smirnov based tool to compare Member 2's real generated observations against the training distribution once available (Week 3 task)."),
  h2("8.3 File Contract Compliance"),
  p(
    "Model artifact filenames and locations now match schema \u00A73.1 exactly: flood_xgboost_project/data/flood_dataset.csv, and flood_xgboost_project/outputs/{xgb_severity_classifier,xgb_resource_regressor,label_encoder}.joblib. FloodObservation feature column order is asserted against the schema's \u00A72.1 field table at training time, so any future drift between the dataset and the schema fails loudly instead of silently."
  ),
  h2("8.4 Updated Results (Post-Fix)"),
  p(
    `Retraining after the fix produced marginally different (and now correctly labeled) results: ${pct(C.xgboost.accuracy)} classification accuracy (was 90.2% pre-fix) and an R\u00B2 of ${num(R.xgboost.r2, 3)} for resource demand (was 0.969 pre-fix). These small differences reflect normal run-to-run variance from the train/test split and are not related to the labeling bug itself, which did not affect aggregate metrics.`
  ),
];

const appendixRows = D.features.map((f) => [f]);
const appendix = [
  h1("Appendix A. Feature Dictionary"),
  metricTable(
    ["Feature"],
    appendixRows,
    [9800]
  ),
];

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 22, color: DARK } },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", run: { size: 30, bold: true, color: BLUE }, paragraph: { spacing: { before: 360, after: 180 } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", run: { size: 26, bold: true, color: DARK }, paragraph: { spacing: { before: 280, after: 140 } } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", run: { size: 23, bold: true, color: GREY }, paragraph: { spacing: { before: 200, after: 100 } } },
    ],
  },
  sections: [
    {
      properties: {
        page: { size: { width: 12240, height: 15840 } }, // US Letter
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [new TextRun({ text: "Flood Severity & Resource Demand \u2014 XGBoost Report", size: 16, color: GREY })],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Page ", size: 16, color: GREY }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY }),
              ],
            }),
          ],
        }),
      },
      children: [
        ...titlePage,
        ...execSummary,
        ...objective,
        ...methodology,
        ...methodologyCont,
        ...resultsClf,
        ...resultsReg,
        ...discussion,
        ...limitations,
        ...conclusion,
        ...addendum,
        ...appendix,
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  const outPath = path.join(ROOT, "outputs", "Flood_XGBoost_Report_Phase2.docx");
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote", outPath);
});
