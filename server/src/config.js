const path = require("path");

// `__dirname` points to `server/src`; ROOT_DIR is `server/`
const ROOT_DIR = path.join(__dirname, "..");

const provider = process.env.AI_PROVIDER || 'ollama';
const ai = {
  provider,
  vision: process.env.AI_VISION === "1",
  baseURL: process.env.AI_BASE_URL || (provider === 'openai' ? 'https://api.openai.com/v1' : 'http://127.0.0.1:11434/v1'),
  model: process.env.AI_MODEL || (provider === 'openai' ? 'gpt-4.1' : 'qwen3.8:27b'),
  apiKey: process.env.AI_API_KEY || (provider === 'openai' ? process.env.OPENAI_API_KEY : undefined),
  timeout: Number(process.env.AI_TIMEOUT_MS || 120000),
};
if (!Number.isFinite(ai.timeout) || ai.timeout <= 0) throw new Error('Invalid AI timeout');
const config = {
  ai,
  wsPort: Number(process.env.WS_PORT || 9885),

  // --- OpenAI Configuration ---
  openai: {
    apiKey: ai.apiKey,
    model: ai.model,
    reasoningEffort: process.env.OPENAI_REASONING_EFFORT || "high",
    reasoningEffortBattle: process.env.OPENAI_REASONING_EFFORT_BATTLE || "high",
    reasoningEffortDialog: process.env.OPENAI_REASONING_EFFORT_DIALOG || "high",
    reasoningEffortCriticism: process.env.OPENAI_REASONING_EFFORT_CRITICISM || "high",
    reasoningEffortSummary: process.env.OPENAI_REASONING_EFFORT_SUMMARY || "xhigh",
    modelPathFinding: ai.model,
    reasoningEffortPathfinding: process.env.OPENAI_REASONING_EFFORT_PATHFINDING || "high",
    reasoningSummary: process.env.OPENAI_REASONING_SUMMARY || "auto",

    tokenLimit: Number(process.env.OPENAI_TOKEN_LIMIT || 250000),
    timeout: Number(process.env.OPENAI_TIMEOUT_MS || 15 * 60 * 1000),
    service_tier: process.env.OPENAI_SERVICE_TIER || "priority",
    service_tierSelfCriticism:
      process.env.OPENAI_SERVICE_TIER_SELF_CRITICISM || process.env.OPENAI_SERVICE_TIER || "priority",
    service_tierSummary: process.env.OPENAI_SERVICE_TIER_SUMMARY || process.env.OPENAI_SERVICE_TIER || "priority",
    service_tierPathfinding: process.env.OPENAI_SERVICE_TIER_PATHFINDING || "priority",

    tokenPrice: {
      "gpt-5.2": { input: 1.75, cached_input: 0.175, output: 14 },
      "gpt-5.1": { input: 1.25, cached_input: 0.125, output: 10 },
      "gpt-5": { input: 1.25, cached_input: 0.125, output: 10 },
      "gpt-4.1": { input: 2, cached_input: 0.5, output: 8 },
      "o4-mini": { input: 1.1, cached_input: 0.275, output: 4.4 },
      "o3": { input: 10, cached_input: 2.5, output: 40 },
    },
  },

  // --- Python Server Configuration (FireRed bridge) ---
  pythonServer: {
    baseUrl: process.env.PYTHON_BASE_URL || "http://127.0.0.1:8000",
    endpoints: {
      requestData: "/requestData",
      minimapSnapshot: "/minimapSnapshot",
      sendCommands: "/sendCommands",
      restartConsole: "/restartConsole",
    },
  },

  // --- Runtime Paths ---
  get dataDir() {
    return process.env.FIRERED_SESSION_DIR || "gpt_data";
  },

  get promptsDir() {
    return path.join(ROOT_DIR, "prompts");
  },

  // --- File Paths ---
  paths: {
    baseDir: ROOT_DIR,

    get dataDir() {
      return config.dataDir;
    },

    get historySaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "history.json");
    },
    get memorySaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "memory.json");
    },
    get objectivesSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "objectives.json");
    },
    get markersSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "markers.json");
    },
    get countersSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "counters.json");
    },
    get badgesSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "badges_log.json");
    },
    get mapVisitsSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "map_visits.json");
    },
    get summariesSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "summaries.json");
    },
    get allSummariesSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "all_summaries.json");
    },
    get progressStepsFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "progress_steps.json");
    },
    get lastVisitedMapsFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "last_visited_maps.json");
    },
    get gameDataJsonFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "game_data.json");
    },
    get lastCriticismSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "last_criticism.txt");
    },
    get tokenUsageFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "token_usage.json");
    },
    get timeUsageFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "time_usage.json");
    },
    get lastUserInputTextSaveFile() {
      return path.resolve(ROOT_DIR, config.dataDir, "last_userInputText_prompt.txt");
    },
  },

  // --- History Processing Configuration ---
  history: {
    keepLastNToolPartialResults: 20,
    keepLastNToolFullResults: 6,
    keepLastNUserMessagesWithMinimap: 1,
    keepLastNUserMessagesWithMemory: 1,
    keepLastNUserMessagesWithViewMap: 5,
    keepLastNUserMessagesWithImages: 10,
    keepLastNUserMessagesWithDetailedData: 4,
    keepLastNUserMessagesWithPokedex: 1,
    limitAssistantMessagesForSelfCriticism: 55,
    limitAssistantMessagesForSummary: 120,
  },

  // --- Tool Configuration ---
  tools: {
    strict: true,
  },

  // --- Loop Configuration ---
  loopDelayMs: 0,
};

const pythonEndpoint = new URL(config.pythonServer.baseUrl);
if (!['127.0.0.1','localhost','[::1]'].includes(pythonEndpoint.hostname))
  throw new Error('Python API must stay local');
module.exports = { config };
