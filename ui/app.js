const API_BASE = "";

const state = {
  data: null,
  hasAnalyzed: false,
  isLoading: false,
  isLive: false,
  aiConfigured: false,
  aiProvider: "",
};

const elements = {
  onboarding: document.querySelector("#onboarding"),
  continueButton: document.querySelector("#continueButton"),
  baseCommit: document.querySelector("#baseCommit"),
  targetCommit: document.querySelector("#targetCommit"),
  analyzeButton: document.querySelector("#analyzeButton"),
  analysisStatus: document.querySelector("#analysisStatus"),
  analysisTitle: document.querySelector("#analysisTitle"),
  assetCount: document.querySelector("#assetCount"),
  riskScore: document.querySelector("#riskScore"),
  riskScoreLarge: document.querySelector("#riskScoreLarge"),
  riskLevel: document.querySelector("#riskLevel"),
  testCount: document.querySelector("#testCount"),
  summaryHeadline: document.querySelector("#summaryHeadline"),
  summaryList: document.querySelector("#summaryList"),
  assetsGrid: document.querySelector("#assetsGrid"),
  riskDrivers: document.querySelector("#riskDrivers"),
  riskArc: document.querySelector("#riskArc"),
  dependencyGraph: document.querySelector("#dependencyGraph"),
  testsList: document.querySelector("#testsList"),
  changesList: document.querySelector("#changesList"),
  aiStatusDot: document.querySelector("#aiBadgeDot"),
  aiStatusText: document.querySelector("#aiStatusText"),
  aiContent: document.querySelector("#aiContent"),
  statusDot: document.querySelector("#statusDot"),
  statusLabel: document.querySelector("#statusLabel"),
  statusDetail: document.querySelector("#statusDetail"),
};

function dismissOnboarding() {
  if (!elements.onboarding) return;
  elements.onboarding.classList.add("is-hidden");
  document.body.classList.remove("onboarding-active");
  window.setTimeout(() => elements.onboarding.remove(), 300);
}

elements.continueButton?.addEventListener("click", dismissOnboarding);

function optionForCommit(commit) {
  const option = document.createElement("option");
  option.value = commit.id;
  option.textContent = commit.label;
  option.title = commit.description;
  return option;
}

function populateSelectors(commits) {
  elements.baseCommit.replaceChildren(...commits.map(optionForCommit));
  elements.targetCommit.replaceChildren(...commits.map(optionForCommit));
  // Default: select the second-to-last as base, last as target
  if (commits.length >= 2) {
    elements.baseCommit.value = commits[1].id;
    elements.targetCommit.value = commits[0].id;
  }
}

function populateSelectorsFromMock(commits) {
  elements.baseCommit.replaceChildren(...commits.base.map(optionForCommit));
  elements.targetCommit.replaceChildren(...commits.target.map(optionForCommit));
}

function renderSummary(summary) {
  elements.summaryHeadline.textContent = summary.headline;
  elements.summaryList.replaceChildren(
    ...summary.items.map((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      return li;
    })
  );
}

function renderAssets(assets) {
  elements.assetsGrid.replaceChildren(
    ...assets.map((asset) => {
      const card = document.createElement("article");
      card.className = "asset-card";
      const riskClass = (asset.risk || "").toLowerCase();
      const impactBadge = asset.impactType
        ? `<span class="tag impact-${asset.impactType}">${asset.changeType}</span>`
        : `<span class="tag ${riskClass}">${asset.risk}</span>`;
      card.innerHTML = `
        <header>
          <div>
            <h3></h3>
            <p></p>
          </div>
          ${impactBadge}
        </header>
        <div class="tags">
          <span class="tag"></span>
          <span class="tag"></span>
        </div>
        <p class="asset-description"></p>
      `;
      card.querySelector("h3").textContent = asset.name;
      card.querySelector("header p").textContent = asset.type;
      const tags = card.querySelectorAll(".tags .tag");
      tags[0].textContent = asset.changeType;
      tags[1].textContent = asset.type;
      card.querySelector(".asset-description").textContent = asset.description;
      return card;
    })
  );
}

function renderRisk(risk) {
  const circumference = 2 * Math.PI * 56;
  const filled = (risk.score / 100) * circumference;
  elements.riskLevel.textContent = `${risk.level} risk`;
  elements.riskScore.textContent = risk.score;
  elements.riskScoreLarge.textContent = risk.score;
  elements.riskArc.style.strokeDasharray = `${filled} ${circumference - filled}`;
  elements.riskDrivers.replaceChildren(
    ...risk.drivers.map((driver) => {
      const li = document.createElement("li");
      li.textContent = driver;
      return li;
    })
  );
}

function renderGraph(dependencies) {
  const nodeById = new Map(dependencies.nodes.map((node) => [node.id, node]));
  elements.dependencyGraph.replaceChildren(
    ...dependencies.edges.map((edge) => {
      const from = nodeById.get(edge.from);
      const to = nodeById.get(edge.to);
      if (!from || !to) return document.createTextNode("");
      const row = document.createElement("div");
      row.className = "flow-row";
      row.innerHTML = `
        <div class="node">
          <strong></strong>
          <span></span>
        </div>
        <div class="edge"></div>
        <div class="node">
          <strong></strong>
          <span></span>
        </div>
      `;
      const nodes = row.querySelectorAll(".node");
      nodes[0].classList.toggle("highlight", Boolean(from.highlight));
      nodes[1].classList.toggle("highlight", Boolean(to.highlight));
      nodes[0].querySelector("strong").textContent = from.label;
      nodes[0].querySelector("span").textContent = from.type;
      row.querySelector(".edge").textContent = `→ ${edge.label}`;
      nodes[1].querySelector("strong").textContent = to.label;
      nodes[1].querySelector("span").textContent = to.type;
      return row;
    })
  );
}

function renderTests(tests) {
  elements.testsList.replaceChildren(
    ...tests.map((test) => {
      const row = document.createElement("article");
      row.className = "test-row";
      row.innerHTML = `
        <div class="priority"></div>
        <div>
          <h3></h3>
          <p></p>
        </div>
      `;
      row.querySelector(".priority").textContent = test.priority;
      row.querySelector("h3").textContent = test.name;
      row.querySelector("p").textContent = test.scenario;
      return row;
    })
  );
}

function renderChanges(changes) {
  if (!elements.changesList) return;
  if (!changes || changes.length === 0) {
    elements.changesList.innerHTML = '<p class="ai-placeholder">No individual changes detected between revisions.</p>';
    return;
  }
  elements.changesList.replaceChildren(
    ...changes.map((change) => {
      const row = document.createElement("article");
      row.className = "change-row";
      row.innerHTML = `
        <div class="change-type"></div>
        <div>
          <h3></h3>
          <p></p>
        </div>
      `;
      row.querySelector(".change-type").textContent = change.type || "MODIFIED";
      row.querySelector("h3").textContent = change.asset || "Asset";
      row.querySelector("p").textContent = change.description || "";
      return row;
    })
  );
}

function renderAIExplanation(ai) {
  if (!elements.aiContent || !elements.aiStatusText) return;
  if (!ai || !ai.available) {
    if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot mock";
    elements.aiStatusText.textContent = (ai && ai.reason) || "AI explanation not configured (optional)";
    elements.aiContent.innerHTML = `
      <p class="ai-placeholder">
        ${(ai && ai.message) || "AI explanation is optional. Configure GEMINI_API_KEY or OPENAI_API_KEY to enable automated natural language insights. Deterministic impact, risk, and regression recommendations are fully functional without AI."}
      </p>
    `;
    return;
  }

  if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot live";
  elements.aiStatusText.textContent = `Generated by ${ai.provider || "AI"}`;

  const container = document.createElement("div");
  if (ai.summary) {
    const summaryDiv = document.createElement("div");
    summaryDiv.className = "ai-section";
    summaryDiv.innerHTML = `<strong>Overview</strong><p></p>`;
    summaryDiv.querySelector("p").textContent = ai.summary;
    container.appendChild(summaryDiv);
  }

  if (ai.sections) {
    for (const [title, content] of Object.entries(ai.sections)) {
      const sectionDiv = document.createElement("div");
      sectionDiv.className = "ai-section";
      sectionDiv.innerHTML = `<strong></strong><p></p>`;
      sectionDiv.querySelector("strong").textContent = title;
      sectionDiv.querySelector("p").textContent = content;
      container.appendChild(sectionDiv);
    }
  }

  elements.aiContent.replaceChildren(container);
}

function renderAnalysis(analysis) {
  elements.analysisStatus.textContent = analysis.status;
  elements.analysisTitle.textContent = analysis.title;
  elements.assetCount.textContent = analysis.affectedAssets.length;
  elements.testCount.textContent = analysis.regressionTests.length;
  renderSummary(analysis.summary);
  renderAssets(analysis.affectedAssets);
  renderRisk(analysis.risk);
  renderChanges(analysis.changes || []);
  renderGraph(analysis.dependencies);
  renderTests(analysis.regressionTests);
  if (analysis.aiExplanation) {
    renderAIExplanation(analysis.aiExplanation);
  }
}

async function checkAIStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/ai-status`);
    if (res.ok) {
      const data = await res.json();
      state.aiConfigured = Boolean(data.configured);
      state.aiProvider = data.provider || "AI";
      if (data.configured) {
        if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot live";
        if (elements.aiStatusText) elements.aiStatusText.textContent = `AI Ready · ${data.provider}`;
        if (elements.aiContent && !state.hasAnalyzed) {
          elements.aiContent.innerHTML = `<p class="ai-placeholder">AI explanation is configured and ready (${data.provider}). Click <strong>Analyze Impact</strong> to generate natural language architecture insights alongside deterministic results.</p>`;
        }
        return;
      }
    }
  } catch {
    // ignore
  }

  state.aiConfigured = false;
  state.aiProvider = "";
  if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot mock";
  if (elements.aiStatusText) elements.aiStatusText.textContent = "AI not configured (optional)";
  if (elements.aiContent && !state.hasAnalyzed) {
    elements.aiContent.innerHTML = `<p class="ai-placeholder">AI explanation is optional. Configure GROK_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in .env.local to enable automated natural language insights. Deterministic impact, risk, and regression recommendations are fully functional without AI.</p>`;
  }
}

function setStatus(mode, label, detail) {
  if (elements.statusDot) {
    elements.statusDot.className = `status-dot ${mode}`;
  }
  if (elements.statusLabel) {
    elements.statusLabel.textContent = label;
  }
  if (elements.statusDetail) {
    elements.statusDetail.textContent = detail;
  }
}

function setLoading(loading) {
  state.isLoading = loading;
  elements.analyzeButton.disabled = loading;
  elements.analyzeButton.textContent = loading ? "Analyzing…" : "Analyze Impact";
  if (loading) {
    elements.analysisStatus.textContent = "Running analysis…";
    elements.analysisTitle.textContent = "Please wait while the analyzer processes the changes";
  }
}

async function tryLiveApi() {
  try {
    const response = await fetch(`${API_BASE}/api/commits`);
    if (!response.ok) return false;
    const data = await response.json();
    if (data.commits && data.commits.length > 0) {
      populateSelectors(data.commits);
      state.isLive = true;
      setStatus("live", "Live mode", "Connected to analyzer");
      checkAIStatus();
      return true;
    }
  } catch {
    // API not available, fall through to mock
  }
  return false;
}

async function loadMockData() {
  const response = await fetch("mock-analysis.json");
  if (!response.ok) {
    throw new Error(`Unable to load mock analysis data: ${response.status}`);
  }
  state.data = await response.json();
  populateSelectorsFromMock(state.data.commits);
  setStatus("mock", "Mock mode", "Demo data ready");
  if (elements.aiStatusText) elements.aiStatusText.textContent = "Mock explanation ready";
}

async function runLiveAnalysis() {
  const base = elements.baseCommit.value;
  const target = elements.targetCommit.value;
  if (!base || !target) return;

  setLoading(true);

  // Set AI card to generating state if configured
  if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot live pulse";
  if (elements.aiStatusText) elements.aiStatusText.textContent = "Generating AI explanation…";
  if (elements.aiContent) {
    elements.aiContent.innerHTML = `<p class="ai-placeholder">Synthesizing natural language architecture insights from deterministic analysis${state.aiProvider ? ` using ${state.aiProvider}` : ""}…</p>`;
  }

  try {
    const url = `${API_BASE}/api/analyze?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`;
    const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
    const data = await response.json();

    if (!response.ok) {
      elements.analysisStatus.textContent = "Analysis error";
      elements.analysisTitle.textContent = data.error || "Unknown error";
      return;
    }

    state.hasAnalyzed = true;
    renderAnalysis(data.analysis);

    // Asynchronously request AI explanation without blocking the UI
    fetch(`${API_BASE}/api/explain?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`, {
      signal: AbortSignal.timeout(25000),
    })
      .then(async (res) => {
        const aiData = await res.json();
        if (res.ok && aiData && aiData.explanation) {
          renderAIExplanation(aiData.explanation);
        } else {
          renderAIExplanation({
            available: false,
            reason: "AI explanation unavailable",
            message: aiData?.error || "Unable to generate AI explanation.",
          });
        }
      })
      .catch((err) => {
        renderAIExplanation({
          available: false,
          reason: "AI explanation timed out",
          message: "The AI explanation request timed out. Deterministic analysis results remain accurate.",
        });
      });
  } catch (error) {
    elements.analysisStatus.textContent = "Connection error";
    elements.analysisTitle.textContent = error.message;
  } finally {
    setLoading(false);
  }
}

elements.analyzeButton.addEventListener("click", () => {
  if (state.isLoading) return;

  if (state.isLive) {
    runLiveAnalysis();
  } else if (state.data) {
    setLoading(true);
    if (elements.aiStatusDot) elements.aiStatusDot.className = "status-dot live pulse";
    if (elements.aiStatusText) elements.aiStatusText.textContent = "Loading analysis & AI insights…";
    setTimeout(() => {
      setLoading(false);
      state.hasAnalyzed = true;
      renderAnalysis(state.data.analysis);
    }, 350);
  }
});

// Sidebar navigation click handler
function initNavTracking() {
  const navLinks = document.querySelectorAll(".nav-item");

  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      navLinks.forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });
}

// Initialize: try live API first, fall back to mock data
(async () => {
  initNavTracking();
  const isLive = await tryLiveApi();
  if (!isLive) {
    await loadMockData().catch((error) => {
      elements.analysisStatus.textContent = "Load error";
      elements.analysisTitle.textContent = error.message;
    });
  }
})();
