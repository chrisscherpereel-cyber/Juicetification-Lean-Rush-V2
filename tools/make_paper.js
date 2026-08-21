// Builds "Juicetification_The_Lean_Rush_paper.docx" — an academic paper on the
// design of the simulation and its contribution to experiential-learning pedagogy.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType, PageBreak,
} = require("docx");

const FONT = "Times New Roman";
const DBL = { line: 480, lineRule: "auto" };
// Resolve paths relative to the repo root so the script runs from anywhere.
const ROOT = path.resolve(__dirname, "..");
const PAPERDIR = path.join(ROOT, "docs", "academic_paper");
const dir = path.join(PAPERDIR, "figures");

// ---- helpers ---------------------------------------------------------------
function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, size: 24, ...opts });
}
// body paragraph, double-spaced, first-line indent
function body(children, { indent = true, align } = {}) {
  if (typeof children === "string") children = [run(children)];
  return new Paragraph({
    children,
    spacing: DBL,
    alignment: align,
    indent: indent ? { firstLine: 720 } : undefined,
  });
}
function title(text) {
  return new Paragraph({
    children: [run(text, { bold: true })],
    spacing: DBL, alignment: AlignmentType.CENTER,
  });
}
function h1(text) {
  return new Paragraph({
    children: [run(text, { bold: true })],
    spacing: { ...DBL, before: 120 }, alignment: AlignmentType.CENTER,
  });
}
function h2(text) {
  return new Paragraph({
    children: [run(text, { bold: true })],
    spacing: { ...DBL, before: 80 },
  });
}
function h3(text) {
  return new Paragraph({
    children: [run(text, { bold: true, italics: true })],
    spacing: DBL,
  });
}
function centered(children) {
  return new Paragraph({ children, spacing: DBL, alignment: AlignmentType.CENTER });
}
// APA-style figure block
function figure(file, w, h, num, ttl, note) {
  return [
    centered([new ImageRun({
      type: "png", data: fs.readFileSync(`${dir}/${file}`),
      transformation: { width: w, height: h },
    })]),
    new Paragraph({ children: [run(`Figure ${num}`, { bold: true })],
      spacing: { before: 120, ...DBL } }),
    new Paragraph({ children: [run(ttl, { italics: true })], spacing: DBL }),
    new Paragraph({ children: [run("Note. ", { italics: true }), run(note)],
      spacing: { ...DBL, after: 120 } }),
  ];
}
function ref(children) {
  return new Paragraph({
    children, spacing: DBL, indent: { left: 720, hanging: 720 },
  });
}

const children = [];
const P = (...xs) => xs.forEach((x) => children.push(x));

// =================== TITLE PAGE ===================
P(new Paragraph({ children: [], spacing: { before: 2400 } }));
P(title("Juicetification: The Lean Rush — Designing a Discrete-Event Simulation for Experiential Lean-Operations Pedagogy"));
P(new Paragraph({ children: [], spacing: DBL }));
P(centered([run("C. Scherpereel")]));
P(centered([run("Northern Arizona University")]));
P(new Paragraph({ children: [], spacing: DBL }));
P(centered([run("Author Note", { italics: true })]));
P(body(
  "Correspondence concerning this article may be addressed to C. Scherpereel, " +
  "Northern Arizona University. Email: chris.scherpereel@nau.edu. The simulation " +
  "described here, Juicetification: The Lean Rush, is an open, single-file " +
  "application and is available from the author.", { indent: false }));
P(new Paragraph({ children: [new PageBreak()] }));

// =================== ABSTRACT ===================
P(h1("Abstract"));
P(body(
  "Lean operations is frequently taught through lecture and case discussion, yet " +
  "its central lessons — that waste is systemic, that the cheapest changes often " +
  "return the most, and that improvement is a disciplined cycle rather than a set " +
  "of tools — are difficult to grasp without doing. This paper reports the design " +
  "and development of Juicetification: The Lean Rush, a browser-based discrete-" +
  "event simulation in which students operate a chaotic juice bar through repeated " +
  "morning rushes and redesign it round by round. The simulation was engineered so " +
  "that authentic lean improvements are rewarded while the classic intuitive traps " +
  "— batching, made-ahead inventory, and gold-plated equipment — visibly backfire, " +
  "allowing learners to discover the seven wastes rather than be told them. The " +
  "design is grounded in experiential-learning theory: each round enacts Kolb's " +
  "(1984) cycle, the inherited mess operationalizes Kapur's (2008) productive " +
  "failure and Mezirow's (1991) disorienting dilemma, guided scaffolding fades " +
  "within the zone of proximal development (Vygotsky, 1978), and a gated debrief " +
  "follows best practice in simulation-based education (Fanning & Gaba, 2007). The " +
  "paper argues that the simulation's principal pedagogical contribution is the " +
  "tight coupling of a lean management routine (Deming's PDCA and Rother's, 2010, " +
  "Coaching Kata) to the instructional loop, so that the method the students learn " +
  "and the method by which they learn it are the same.", { indent: false }));
P(new Paragraph({ children: [run("Keywords: ", { italics: true }),
  run("experiential learning, lean operations, simulation-based education, kaizen, productive failure, debriefing")],
  spacing: DBL }));
P(new Paragraph({ children: [new PageBreak()] }));

// =================== INTRODUCTION ===================
P(title("Juicetification: The Lean Rush — Designing a Discrete-Event Simulation for Experiential Lean-Operations Pedagogy"));
P(body(
  "Lean operations occupies an awkward position in the operations-management " +
  "curriculum. Its vocabulary — the seven wastes, 5S, standard work, pull, kaizen " +
  "— is easy to state and hard to feel. Students can recite that overproduction is " +
  "waste while still believing, at the level of intuition that governs their " +
  "decisions, that making drinks ahead of time must speed service up. Traditional " +
  "instruction compounds the problem: a lecture on the seven wastes presents lean " +
  "as a checklist of virtues rather than as a set of counter-intuitive, cost-" +
  "constrained trade-offs. Active-learning scholarship has long argued that such " +
  "material is better learned by doing than by listening (Bonwell & Eison, 1991), " +
  "and business-simulation research consistently finds that well-designed " +
  "simulations improve higher-order operational reasoning relative to lecture " +
  "alone (Anderson & Lawton, 2009; Salas et al., 2009)."));
P(body(
  "This paper describes the design and development of Juicetification: The Lean " +
  "Rush, a discrete-event simulation built to make the seven wastes experiential. " +
  "The learner inherits a disorganized juice bar — stations out of sequence, large " +
  "blend batches, a pile of pre-made cups — and runs it through a 15-minute " +
  "morning rush. After each rush the shop is diagnosed, a coach poses a single " +
  "Socratic question, the learner redesigns one aspect of the operation, predicts " +
  "the effect, and runs again. The remainder of the paper situates the design in " +
  "learning theory, walks through the development decisions that follow from that " +
  "theory, and argues for the simulation's specific contribution to experiential-" +
  "learning pedagogy: the fusion of the object of study (a lean improvement " +
  "routine) with the mechanism of instruction (an experiential improvement loop)."));

// =================== THEORETICAL FRAMEWORK ===================
P(h1("Theoretical Framework"));
P(body(
  "The design rests on two literatures — the operations-management canon that " +
  "defines the content, and the learning sciences that define how that content is " +
  "best acquired. On the content side, the seven wastes and the ideal of one-piece " +
  "flow derive from the Toyota Production System (Ohno, 1988) and its Western " +
  "synthesis in lean thinking (Womack & Jones, 2003); the improvement cycle is " +
  "Deming's (1986) Plan-Do-Check-Act. On the learning side, the organizing frame " +
  "is Kolb's (1984) experiential-learning cycle, in which knowledge is created " +
  "through the transformation of experience across four modes: concrete " +
  "experience, reflective observation, abstract conceptualization, and active " +
  "experimentation."));
P(body(
  "Three further principles shape the design. First, productive failure (Kapur, " +
  "2008) holds that allowing learners to grapple with a problem before instruction " +
  "produces deeper conceptual understanding than instruction first; the inherited, " +
  "deliberately broken shop is a designed failure experience. The overproduction " +
  "trap, in which the intuitive move to batch and pre-make drinks measurably harms " +
  "performance, is also a disorienting dilemma in Mezirow's (1991) sense — a " +
  "confrontation between prior belief and evidence that is the trigger for " +
  "transformative learning. Second, learning is scaffolded within the zone of " +
  "proximal development (Vygotsky, 1978; Wood et al., 1976): the simulation " +
  "surfaces only the decision the learner is ready to act on, then withdraws that " +
  "support toward independent “free play.” Third, extraneous cognitive " +
  "load is minimized (Sweller, 1988) by revealing one actionable waste at a time " +
  "rather than the full instrument at once, reserving working memory for the lean " +
  "concepts themselves. Feedback throughout is designed as feed-forward in Hattie " +
  "and Timperley's (2007) terms, answering not only “how am I doing?” but " +
  "“where to next?”"));

// =================== DESIGN AND DEVELOPMENT ===================
P(h1("Design and Development of the Simulation"));

P(h2("Simulation Architecture"));
P(body(
  "Juicetification: The Lean Rush is implemented as a single-file web application " +
  "with an embedded discrete-event engine. Customer arrivals during the rush " +
  "follow a non-homogeneous Poisson process generated by thinning, so demand peaks " +
  "and ebbs within the 15-minute window. Each order flows through a fixed process " +
  "route (cups, fruit, ice, blender, finishing, pickup); stations contend for a " +
  "shared pool of staff and blenders, customers abandon the queue when their " +
  "patience is exhausted, and made-ahead or mis-made drinks generate spoilage and " +
  "rework. Every configuration is evaluated over multiple stochastic replications, " +
  "so the learner is shown not only an average outcome but the spread across " +
  "rushes, making variability — and therefore the value of standard work — " +
  "visible. Crucially, each session is instantiated from a random but always-" +
  "solvable scenario (a scrambled layout, an inherited batch size and pre-made " +
  "pile, one covertly slow station, and a demand level), so that no two students " +
  "face the same optimum and answers cannot be copied."));

P(h2("The Kaizen Loop as Instructional Spine"));
P(body(
  "The simulation's most consequential design decision is to make the screen " +
  "itself one turn of the PDCA cycle, and to align that cycle explicitly with " +
  "Kolb's (1984) four modes (see Figure 1). The learner runs the rush (Do / " +
  "concrete experience), reads the resulting waste and 5S dashboards (Check / " +
  "reflective observation), works with the coach to name the dominant waste and " +
  "the lean principle it violates (Act / abstract conceptualization), and then " +
  "chooses, predicts, and commits a counter-measure (Plan / active " +
  "experimentation) before running again. Because the Act phase flows directly " +
  "into the next Plan, the loop is experienced as continuous improvement rather " +
  "than as discrete exercises — the structure is kaizen, and it is named as such " +
  "for the learner. This satisfies a recurring recommendation in the transfer " +
  "literature that learners rarely transfer a strategy they cannot name (Perkins & " +
  "Salomon, 1988)."));
P(...figure("fig1_kolb_pdca.png", 600, 397, 1,
  "Kolb's Experiential-Learning Cycle Mapped onto the Simulation's PDCA Game Loop",
  "Each round of the simulation traverses all four modes of Kolb's (1984) cycle, " +
  "labeled for the learner with the corresponding Plan-Do-Check-Act phase and the " +
  "concrete on-screen activity."));

P(h2("Making Waste Visible"));
P(body(
  "Abstract categories become learnable when they are rendered perceptible. The " +
  "simulation therefore visualizes each waste rather than merely scoring it. The " +
  "clearest example is transport waste: the process is drawn as a flow diagram in " +
  "which forward movement between stations is shown as green arcs above the line " +
  "and backtracking is shown as red arcs below it (see Figure 2). A scrambled " +
  "layout produces a tangle of red; dragging the stations into process order turns " +
  "the diagram green and shortens the walking path. The learner does not need the " +
  "word “transport” defined; the waste is seen and then removed, and the " +
  "label is attached to an experience the learner has already had. Inventory, " +
  "motion, and defects are surfaced through comparable visual dashboards, " +
  "supporting the multimedia principle that pairing a named concept with a " +
  "concrete representation reduces the load of holding the abstraction alone " +
  "(Sweller, 1988)."));
P(...figure("fig2_flow_waste.png", 600, 413, 2,
  "Transport Waste Made Perceptible in the Process-Flow Diagram",
  "Panel (a) shows the inherited, scrambled layout, in which the drink repeatedly " +
  "doubles back (red arcs, below the line). Panel (b) shows the same process after " +
  "the learner orders the stations, leaving only forward flow (green arcs, above " +
  "the line)."));

P(h2("The Coaching Kata and Socratic Scaffolding"));
P(body(
  "The Act phase is delivered by a coach modeled on Rother's (2010) Coaching Kata, " +
  "the five-question routine by which a Toyota manager develops a learner: what is " +
  "the target condition; what is the actual condition; what obstacle is now in the " +
  "way; what is the next step; and when can we see what we have learned. This " +
  "choice is deliberate and, we argue, distinctive: the coaching method is itself " +
  "an authentic lean-management practice, so the pedagogy models the very " +
  "discipline it teaches. The coach requires the learner to commit to a diagnosis " +
  "before the simulation can be run again, enforcing reflection rather than " +
  "trial-and-error clicking. Consistent with a Socratic stance and with evidence " +
  "that premature answers depress learning (Kapur, 2008), the coach withholds its " +
  "specific recommendation until the learner explicitly requests help; when it does " +
  "advise, it points to the counter-measure that would most improve profitability " +
  "at that moment and opens exactly that decision, giving Hattie and Timperley's " +
  "(2007) “where to next” in a single, actionable step."));

P(h2("The Lean Score, Prediction, and the Cost–Benefit Judgment"));
P(body(
  "Performance is summarized in a 0–100 Lean Score composed of five per-unit " +
  "rates — waste, correctly served customers, quality, speed, and flow — with " +
  "waste weighted most heavily because its elimination is the core of lean and " +
  "because doing so prevents the overproduction strategy from ever scoring well. " +
  "Expressing every dimension as a rate rather than an absolute count was a " +
  "necessary refinement: an earlier additive-penalty formulation floored the score " +
  "of any busy shop near zero and thereby hid incremental progress, undermining the " +
  "feedback loop. The revised score rises smoothly as counter-measures accumulate " +
  "(see Figure 3), so that each genuine improvement is registered — an application " +
  "of the principle that feedback must be legible to function as feedback rather " +
  "than as an opaque grade (Hattie & Timperley, 2007)."));
P(body(
  "Two mechanisms make the cost–benefit judgment — arguably the most " +
  "sophisticated reasoning the simulation demands — experiential. First, before " +
  "each run the learner commits a prediction of the plan's effect and is shown, " +
  "the following round, whether that prediction held; this predict-then-observe " +
  "structure is a metacognitive calibration exercise. Second, every lean practice " +
  "carries a realistic per-rush upkeep cost, so “lean is always good” is " +
  "not a winning strategy. Figure 3 illustrates the resulting tension directly: as " +
  "the learner adopts one-piece flow before the bottleneck has been relieved, the " +
  "Lean Score continues to climb while profit collapses, recovering only once " +
  "capacity is right-sized. The end-of-game reveal (see Figure 4) then shows that " +
  "the cheapest organizing moves — ordering the line, basic 5S, recipe cards — " +
  "returned far more per dollar than the expensive ones, the empirical answer to " +
  "the question of what to do first. Withholding this analysis until the debrief " +
  "is intentional: the learner is meant to discover the priority ladder, not to be " +
  "handed it."));
P(...figure("fig3_trajectory.png", 600, 351, 3,
  "Lean Score and Profit Across a Guided Four-Round Improvement Arc",
  "Data are from the simulation engine for a representative scenario. The Lean " +
  "Score (left axis) rises monotonically as wastes are removed. Profit (right " +
  "axis) falls sharply when one-piece flow is adopted before capacity is right-" +
  "sized and rebounds once the bottleneck is relieved, dramatizing the cost–" +
  "benefit and sequencing lessons."));
P(...figure("fig4_impact_effort.png", 600, 396, 4,
  "Impact Versus Effort for Each Intervention in the Final Shop",
  "A leave-one-out analysis computed by the engine: each point is the profit lost " +
  "if that single intervention were reverted, plotted against its cost. Cheap " +
  "organizing changes cluster at high return per dollar; added capacity is " +
  "expensive and, once flow is fixed, contributes least."));

P(h2("Debriefing and Constructive Alignment"));
P(body(
  "The most robust finding in simulation-based education is that most learning " +
  "occurs in the debrief rather than in the doing (Fanning & Gaba, 2007). The " +
  "simulation therefore treats the debrief as the summative event and gates it: " +
  "the core game is complete only when the learner has met three objectives " +
  "simultaneously — all seven wastes addressed, a Lean Score of at least 70, and a " +
  "profitable shop — a stopping rule that guarantees the learning objectives have " +
  "actually been achieved rather than a round count elapsed. The debrief then " +
  "walks the whole arc: it tabulates how each waste was tackled, narrates the " +
  "learner's trajectory, reveals the return on each of the learner's own " +
  "decisions, and, following Rudolph et al.'s (2007) “debriefing with good " +
  "judgment,” asks the learner to reconstruct their reasoning through four " +
  "written reflections and a short knowledge check. The downloadable report — and " +
  "hence course credit — is released only when these are complete, an instance of " +
  "constructive alignment in which the assessed artifact is the reasoning, not the " +
  "score (Biggs, 1996). Framing the graded product as reflection rather than points " +
  "also guards against the goal-displacement risk that gamified metrics can crowd " +
  "out understanding (Deci & Ryan, 2000)."));

// =================== CONTRIBUTION ===================
P(h1("Contribution to Experiential-Learning Pedagogy"));
P(body(
  "The simulation's contribution is less any single feature than the systematic " +
  "translation of learning-science principles into concrete mechanics, summarized " +
  "in Figure 5. Several general lessons for the design of experiential learning " +
  "environments follow."));
P(...figure("fig5_theory_map.png", 600, 449, 5,
  "Mapping of Learning-Science Principles to Design Features",
  "Each principle in the learning-sciences literature is realized as a specific, " +
  "inspectable mechanic in the simulation rather than as a general aspiration."));
P(body(
  "First, and most distinctively, the simulation collapses the distinction between " +
  "the method taught and the method of teaching. The learner is taught kaizen and " +
  "the Coaching Kata, and is taught them by being run through a kaizen loop by a " +
  "coaching kata. This reflexive alignment is unusual: most simulations teach a " +
  "domain through a generic game loop, whereas here the loop is itself a faithful " +
  "instance of the domain's core practice. The pedagogical payoff is transfer " +
  "(Perkins & Salomon, 1988) — the learner leaves with a portable improvement " +
  "routine, not merely facts about a juice bar, and the closing reflection " +
  "explicitly bridges to a process in the learner's own life or workplace."));
P(body(
  "Second, the design demonstrates that productive failure and cognitive-load " +
  "management, sometimes treated as opposing commitments, can be reconciled by " +
  "sequencing. The learner is permitted — indeed engineered — to fail on the " +
  "inherited shop and on the overproduction trap (Kapur, 2008; Mezirow, 1991), but " +
  "the interface simultaneously constrains attention to one actionable decision at " +
  "a time (Sweller, 1988). Struggle is located in the conceptual trade-off, not in " +
  "navigating the instrument."));
P(body(
  "Third, the simulation shows how affordable simulation can move beyond Chi and " +
  "Wylie's (2014) “active” tier toward “constructive” " +
  "engagement by requiring learners to generate predictions, justify diagnoses, " +
  "and author reflections rather than merely select options. While the present " +
  "version is single-player, its randomized scenarios are designed to support the " +
  "further, “interactive” tier: because each learner confronts a " +
  "different optimum, comparing strategies across a class becomes a substantive " +
  "discussion rather than an answer-checking exercise."));

// =================== DISCUSSION / LIMITATIONS ===================
P(h1("Discussion and Limitations"));
P(body(
  "The claims advanced here are design claims, grounded in theory and in the " +
  "behavior of the instrument, not yet empirical claims about learning gains. The " +
  "most important next step is evaluation: a pre/post knowledge measure paired with " +
  "the reflection rubric would test whether the theorized mechanisms produce " +
  "measurable understanding, and a comparison against a lecture or static-case " +
  "control would situate the effect. Several design limitations also bound the " +
  "contribution. The engine models a single, deliberately simple service process, " +
  "which aids clarity but abstracts away supply variability and multi-product " +
  "complexity; the Lean Score, though now legible and monotonic on the guided " +
  "path, embeds weighting choices that are pedagogical rather than empirical; and " +
  "the current single-player form realizes the social, interactive tier of " +
  "engagement only latently. Deliberate-practice extensions — single-waste drills " +
  "with immediate feedback (Ericsson et al., 1993) — and a collaborative mode are " +
  "natural directions for subsequent versions."));

// =================== CONCLUSION ===================
P(h1("Conclusion"));
P(body(
  "Juicetification: The Lean Rush was built on the premise that the seven wastes " +
  "are best discovered, not declared. By enacting Kolb's cycle every round, " +
  "engineering a productive failure to be overcome, scaffolding attention within " +
  "the learner's zone of proximal development, and gating a rigorous debrief behind " +
  "genuine reflection, the simulation turns a set of counter-intuitive operational " +
  "trade-offs into lived experience. Its central pedagogical move — making the " +
  "improvement routine that is the object of study also the loop through which " +
  "study occurs — offers a transferable template for teaching any disciplined, " +
  "iterative practice. Whether that template delivers the learning gains its design " +
  "predicts is an empirical question the instrument is now positioned to answer."));

// =================== REFERENCES ===================
P(new Paragraph({ children: [new PageBreak()] }));
P(h1("References"));
const R = [
  [run("Anderson, P. H., & Lawton, L. (2009). Business simulations and cognitive learning: Developments, desires, and future directions. "),
   run("Simulation & Gaming, 40", { italics: true }), run("(2), 193–216.")],
  [run("Biggs, J. (1996). Enhancing teaching through constructive alignment. "),
   run("Higher Education, 32", { italics: true }), run("(3), 347–364.")],
  [run("Bonwell, C. C., & Eison, J. A. (1991). "),
   run("Active learning: Creating excitement in the classroom", { italics: true }),
   run(" (ASHE-ERIC Higher Education Report No. 1). The George Washington University.")],
  [run("Chi, M. T. H., & Wylie, R. (2014). The ICAP framework: Linking cognitive engagement to active learning outcomes. "),
   run("Educational Psychologist, 49", { italics: true }), run("(4), 219–243.")],
  [run("Deci, E. L., & Ryan, R. M. (2000). The “what” and “why” of goal pursuits: Human needs and the self-determination of behavior. "),
   run("Psychological Inquiry, 11", { italics: true }), run("(4), 227–268.")],
  [run("Deming, W. E. (1986). "), run("Out of the crisis", { italics: true }),
   run(". MIT Center for Advanced Engineering Study.")],
  [run("Ericsson, K. A., Krampe, R. T., & Tesch-Römer, C. (1993). The role of deliberate practice in the acquisition of expert performance. "),
   run("Psychological Review, 100", { italics: true }), run("(3), 363–406.")],
  [run("Fanning, R. M., & Gaba, D. M. (2007). The role of debriefing in simulation-based learning. "),
   run("Simulation in Healthcare, 2", { italics: true }), run("(2), 115–125.")],
  [run("Hattie, J., & Timperley, H. (2007). The power of feedback. "),
   run("Review of Educational Research, 77", { italics: true }), run("(1), 81–112.")],
  [run("Kapur, M. (2008). Productive failure. "),
   run("Cognition and Instruction, 26", { italics: true }), run("(3), 379–424.")],
  [run("Kolb, D. A. (1984). "),
   run("Experiential learning: Experience as the source of learning and development", { italics: true }),
   run(". Prentice Hall.")],
  [run("Mezirow, J. (1991). "),
   run("Transformative dimensions of adult learning", { italics: true }), run(". Jossey-Bass.")],
  [run("Ohno, T. (1988). "),
   run("Toyota production system: Beyond large-scale production", { italics: true }),
   run(". Productivity Press.")],
  [run("Perkins, D. N., & Salomon, G. (1988). Teaching for transfer. "),
   run("Educational Leadership, 46", { italics: true }), run("(1), 22–32.")],
  [run("Rother, M. (2010). "),
   run("Toyota kata: Managing people for improvement, adaptiveness, and superior results", { italics: true }),
   run(". McGraw-Hill.")],
  [run("Rudolph, J. W., Simon, R., Rivard, P., Dufresne, R. L., & Raemer, D. B. (2007). Debriefing with good judgment: Combining rigorous feedback with genuine inquiry. "),
   run("Anesthesiology Clinics, 25", { italics: true }), run("(2), 361–376.")],
  [run("Salas, E., Wildman, J. L., & Piccolo, R. F. (2009). Using simulation-based training to enhance management education. "),
   run("Academy of Management Learning & Education, 8", { italics: true }), run("(4), 559–573.")],
  [run("Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. "),
   run("Cognitive Science, 12", { italics: true }), run("(2), 257–285.")],
  [run("Vygotsky, L. S. (1978). "),
   run("Mind in society: The development of higher psychological processes", { italics: true }),
   run(". Harvard University Press.")],
  [run("Womack, J. P., & Jones, D. T. (2003). "),
   run("Lean thinking: Banish waste and create wealth in your corporation", { italics: true }),
   run(" (2nd ed.). Free Press.")],
  [run("Wood, D., Bruner, J. S., & Ross, G. (1976). The role of tutoring in problem solving. "),
   run("Journal of Child Psychology and Psychiatry, 17", { italics: true }), run("(2), 89–100.")],
];
R.forEach((c) => P(ref(c)));

const doc = new Document({
  creator: "Juicetification: The Lean Rush",
  styles: { default: { document: { run: { font: FONT, size: 24 } } } },
  sections: [{
    properties: { page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
    } },
    children,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  const out = path.join(PAPERDIR, "Juicetification_The_Lean_Rush_paper.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
