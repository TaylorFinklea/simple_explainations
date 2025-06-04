<script setup lang="ts">
import { ref, onMounted } from "vue";
import { API_CONFIG } from "../config";

interface PredictionResult {
  word: string;
  probability: number;
  tokenId: number;
}

interface PredictionResponse {
  word: string;
  probability: number;
  token_id: number;
}

const inputPhrase = ref("The wheels on the bus go");
const topKTokens = ref(5);
const predictions = ref<PredictionResult[]>([]);
const isLoading = ref(false);
const error = ref("");
const connectionStatus = ref<"checking" | "connected" | "disconnected">(
  "checking",
);
const modelStatus = ref<"not_loaded" | "loading" | "loaded" | "error">(
  "not_loaded",
);
const continuingWithWord = ref("");
const isLoadingModel = ref(false);
const isRateLimited = ref(false);
const rateLimitRetryIn = ref(0);
let rateLimitTimer: ReturnType<typeof setInterval> | null = null;

const checkModelStatus = async () => {
  try {
    const response = await fetch(API_CONFIG.modelStatusEndpoint);
    if (response.ok) {
      const data = await response.json();
      modelStatus.value = data.status;
      return data.status;
    }
  } catch (err: unknown) {
    console.error("Model status check failed:", err);
  }
  return "error";
};

const loadModel = async () => {
  isLoadingModel.value = true;
  error.value = "";

  try {
    const response = await fetch(API_CONFIG.modelLoadEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      if (data.status === "success" || data.status === "already_loaded") {
        modelStatus.value = "loaded";
      } else if (data.status === "already_loading") {
        modelStatus.value = "loading";
        // Poll for completion
        await pollModelStatus();
      }
    } else {
      modelStatus.value = "error";
      error.value = "Failed to load model";
    }
  } catch (err: unknown) {
    modelStatus.value = "error";
    if (err instanceof Error) {
      error.value = `Model loading failed: ${err.message}`;
    } else {
      error.value = "An unknown error occurred during model loading";
    }
    console.error("Model loading error:", err);
  } finally {
    isLoadingModel.value = false;
  }
};

const pollModelStatus = async () => {
  const maxAttempts = 60; // 2 minutes with 2-second intervals
  let attempts = 0;

  const poll = async () => {
    if (attempts >= maxAttempts) {
      modelStatus.value = "error";
      error.value = "Model loading timed out";
      return;
    }

    const status = await checkModelStatus();
    if (status === "loaded") {
      return;
    } else if (status === "error") {
      error.value = "Model loading failed";
      return;
    } else if (status === "loading") {
      attempts++;
      setTimeout(poll, 2000); // Check again in 2 seconds
    }
  };

  await poll();
};

const runPrediction = async () => {
  if (!inputPhrase.value.trim()) {
    error.value = "Please enter a phrase";
    return;
  }

  // Check model status first
  const currentModelStatus = await checkModelStatus();
  if (currentModelStatus !== "loaded") {
    if (currentModelStatus === "not_loaded") {
      error.value = "Model is not loaded. Please load the model first.";
      return;
    } else if (currentModelStatus === "loading") {
      error.value = "Model is currently loading. Please wait...";
      return;
    } else if (currentModelStatus === "error") {
      error.value = "Model failed to load. Please try loading it again.";
      return;
    }
  }

  isLoading.value = true;
  error.value = "";
  predictions.value = [];

  try {
    const response = await fetch(API_CONFIG.predictEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        input_phrase: inputPhrase.value,
        top_k_tokens: topKTokens.value,
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        // Handle rate limiting
        const errorData = await response.json();
        handleRateLimit();
        return;
      } else {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `HTTP error! status: ${response.status}`,
        );
      }
    }

    const result = await response.json();
    predictions.value = result.predictions.map((pred: PredictionResponse) => ({
      word: pred.word,
      probability: pred.probability,
      tokenId: pred.token_id,
    }));

    // Clear any rate limiting state on successful request
    isRateLimited.value = false;
    rateLimitRetryIn.value = 0;
    if (rateLimitTimer) {
      clearInterval(rateLimitTimer);
      rateLimitTimer = null;
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        error.value =
          "Cannot connect to AI server. Make sure the backend is running on http://localhost:8000";
        connectionStatus.value = "disconnected";
      } else {
        error.value = `Failed to get predictions: ${err.message}`;
      }
    } else {
      error.value = "An unknown error occurred";
    }
    console.error("Prediction error:", err);
  } finally {
    isLoading.value = false;
  }
};

const formatPercentage = (probability: number) => {
  return (probability * 100).toFixed(1) + "%";
};

const continueWithPrediction = async (word: string) => {
  // Set loading state for this specific word
  continuingWithWord.value = word;

  // Add the selected word to the input phrase
  inputPhrase.value = `${inputPhrase.value} ${word}`.trim();

  // Automatically run a new prediction with the updated phrase
  await runPrediction();

  // Clear the continuing state
  continuingWithWord.value = "";
};

const handleRateLimit = () => {
  isRateLimited.value = true;
  rateLimitRetryIn.value = 60; // 60 seconds countdown

  // Clear any existing timer
  if (rateLimitTimer) {
    clearInterval(rateLimitTimer);
  }

  // Start countdown timer
  rateLimitTimer = setInterval(() => {
    rateLimitRetryIn.value--;
    if (rateLimitRetryIn.value <= 0) {
      isRateLimited.value = false;
      if (rateLimitTimer) {
        clearInterval(rateLimitTimer);
        rateLimitTimer = null;
      }
    }
  }, 1000);
};

const retryAfterRateLimit = () => {
  isRateLimited.value = false;
  rateLimitRetryIn.value = 0;
  if (rateLimitTimer) {
    clearInterval(rateLimitTimer);
    rateLimitTimer = null;
  }
  // Automatically try the prediction again
  runPrediction();
};

const clearPhrase = () => {
  inputPhrase.value = "";
  predictions.value = [];
  error.value = "";
};

const checkServerConnection = async () => {
  connectionStatus.value = "checking";
  try {
    const response = await fetch(API_CONFIG.healthEndpoint);
    if (response.ok) {
      connectionStatus.value = "connected";
      // Also check model status when server is connected
      await checkModelStatus();
    } else {
      connectionStatus.value = "disconnected";
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      console.error("Server connection failed:", err.message);
    } else {
      console.error("Server connection failed:", err);
    }
    connectionStatus.value = "disconnected";
  }
};

// Check connection on component mount
onMounted(() => {
  checkServerConnection();
});
</script>

<template>
  <div class="max-w-4xl mx-auto px-4">
    <!-- Page Header -->
    <div class="text-center mb-8">
      <h2 class="text-2xl font-bold text-gray-900 mb-2">
        Interactive Word Prediction
      </h2>
      <p class="text-gray-600">
        Enter a phrase and see what the AI thinks comes next
      </p>
    </div>

    <!-- Server Status Card -->
    <div
      v-if="connectionStatus === 'disconnected'"
      class="card mb-6 bg-red-50 border-red-200"
    >
      <div class="flex items-center space-x-2">
        <div class="w-3 h-3 bg-red-600 rounded-full"></div>
        <span class="text-red-800 font-medium">Backend Server Not Running</span>
      </div>
      <p class="text-red-700 text-sm mt-1 mb-3">
        Please start the FastAPI server to use the AI predictions.
      </p>
      <div class="bg-gray-100 p-2 rounded text-sm">
        <code>cd how-ai-works && uv run ai-server</code>
      </div>
    </div>

    <!-- Rate Limit Status Card -->
    <div v-if="isRateLimited" class="card mb-6 bg-orange-50 border-orange-200">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center space-x-2">
            <div class="w-3 h-3 bg-orange-600 rounded-full"></div>
            <span class="text-orange-800 font-medium">Rate Limit Reached</span>
          </div>
          <p class="text-orange-700 text-sm mt-1">
            You've made too many predictions recently. Please wait
            {{ rateLimitRetryIn }} seconds before trying again.
          </p>
          <p class="text-orange-600 text-xs mt-2">
            💡 <strong>Tip:</strong> The API allows 30 predictions per minute to
            ensure fair usage for all users.
          </p>
        </div>
        <button
          v-if="rateLimitRetryIn <= 0"
          @click="retryAfterRateLimit"
          class="btn-primary"
        >
          Try Again
        </button>
        <div v-else class="text-orange-600 font-mono text-lg">
          {{ rateLimitRetryIn }}s
        </div>
      </div>
    </div>

    <!-- Model Loading Status Card (only show when model is not loaded) -->
    <div
      v-if="connectionStatus === 'connected' && modelStatus !== 'loaded'"
      class="card mb-6"
    >
      <!-- Model Not Loaded -->
      <div
        v-if="modelStatus === 'not_loaded'"
        class="bg-yellow-50 border-yellow-200 p-4 rounded-lg"
      >
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center space-x-2">
              <div class="w-3 h-3 bg-yellow-600 rounded-full"></div>
              <span class="text-yellow-800 font-medium"
                >AI Model Not Loaded</span
              >
            </div>
            <p class="text-yellow-700 text-sm mt-1">
              The AI model needs to be loaded before you can make predictions.
              This is a one-time process.
            </p>
          </div>
          <button
            @click="loadModel"
            :disabled="isLoadingModel"
            class="btn-primary"
          >
            <span v-if="isLoadingModel">Loading...</span>
            <span v-else>Load AI Model</span>
          </button>
        </div>
      </div>

      <!-- Model Loading -->
      <div
        v-else-if="modelStatus === 'loading' || isLoadingModel"
        class="bg-blue-50 border-blue-200 p-4 rounded-lg"
      >
        <div class="flex items-center space-x-3">
          <div
            class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"
          ></div>
          <div>
            <div class="text-blue-800 font-medium">Loading AI Model...</div>
            <p class="text-blue-700 text-sm mt-1">
              This may take 1-2 minutes for the first time. The model
              (SmolLM2-1.7B) is being downloaded and initialized.
            </p>
            <div class="mt-2 text-xs text-blue-600">
              ⏳ Please wait, do not refresh the page
            </div>
          </div>
        </div>
      </div>

      <!-- Model Error -->
      <div
        v-else-if="modelStatus === 'error'"
        class="bg-red-50 border-red-200 p-4 rounded-lg"
      >
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center space-x-2">
              <div class="w-3 h-3 bg-red-600 rounded-full"></div>
              <span class="text-red-800 font-medium">Model Loading Failed</span>
            </div>
            <p class="text-red-700 text-sm mt-1">
              There was an error loading the AI model. Please try again.
            </p>
          </div>
          <button
            @click="loadModel"
            :disabled="isLoadingModel"
            class="btn-primary"
          >
            <span v-if="isLoadingModel">Retrying...</span>
            <span v-else>Retry Loading</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Input Section -->
    <div class="card mb-8">
      <div class="space-y-4">
        <div>
          <label
            for="phrase"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Input Phrase
          </label>
          <input
            id="phrase"
            v-model="inputPhrase"
            type="text"
            class="input-field"
            placeholder="Enter a phrase..."
            @keyup.enter="runPrediction"
            :disabled="
              connectionStatus !== 'connected' || modelStatus !== 'loaded'
            "
          />
        </div>

        <div>
          <label
            for="topK"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Number of Predictions
          </label>
          <input
            id="topK"
            v-model.number="topKTokens"
            type="number"
            min="1"
            max="10"
            class="input-field w-32"
            :disabled="
              connectionStatus !== 'connected' || modelStatus !== 'loaded'
            "
          />
        </div>

        <div class="flex space-x-2">
          <button
            @click="runPrediction"
            :disabled="
              isLoading ||
              connectionStatus !== 'connected' ||
              modelStatus !== 'loaded' ||
              isRateLimited
            "
            class="btn-primary"
          >
            <span v-if="isLoading">Predicting...</span>
            <span v-else-if="connectionStatus !== 'connected'"
              >Server Disconnected</span
            >
            <span v-else-if="modelStatus === 'loading'">Model Loading...</span>
            <span v-else-if="modelStatus === 'not_loaded'"
              >Load Model First</span
            >
            <span v-else-if="modelStatus === 'error'">Model Error</span>
            <span v-else-if="isRateLimited"
              >Rate Limited ({{ rateLimitRetryIn }}s)</span
            >
            <span v-else>Predict Next Word</span>
          </button>

          <button
            @click="clearPhrase"
            :disabled="isLoading || !inputPhrase.trim()"
            class="btn-secondary"
            title="Clear phrase and start over"
          >
            Clear
          </button>
        </div>
      </div>

      <!-- Error Message -->
      <div
        v-if="error"
        class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6"
      >
        <div class="flex">
          <div class="text-red-600 text-sm">{{ error }}</div>
        </div>
      </div>

      <!-- Results Section -->
      <div v-if="predictions.length > 0" class="card">
        <h2 class="text-xl font-semibold text-gray-900 mb-4">Predictions</h2>

        <!-- Complete sentence preview -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div class="text-sm font-medium text-blue-900 mb-2">
            Complete sentence with top prediction:
          </div>
          <div class="text-blue-800 mb-3">
            "{{ inputPhrase }} {{ predictions[0]?.word }}"
          </div>

          <!-- Phrase building visualization -->
          <div class="border-t border-blue-200 pt-3">
            <div class="text-xs font-medium text-blue-700 mb-2">
              Current phrase breakdown:
            </div>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="(word, index) in inputPhrase.split(' ')"
                :key="`${word}-${index}`"
                class="px-2 py-1 bg-white border border-blue-200 rounded text-xs text-blue-800"
                :class="{
                  'bg-blue-100 border-blue-300 font-medium':
                    index === inputPhrase.split(' ').length - 1,
                }"
                :title="
                  index === inputPhrase.split(' ').length - 1
                    ? 'Most recently added word'
                    : `Word ${index + 1}`
                "
              >
                {{ word }}
              </span>
              <span
                class="px-2 py-1 bg-green-50 border border-green-200 rounded text-xs text-green-600 font-medium"
              >
                {{ predictions[0]?.word || "?" }}
              </span>
            </div>
          </div>
        </div>

        <!-- Instructions -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <p class="text-blue-800 text-sm">
            💡 <strong>Tip:</strong> Click on any predicted word to add it to
            your phrase and continue the prediction!
            <span v-if="continuingWithWord" class="block mt-1 text-blue-600">
              ⏳ Adding "{{ continuingWithWord }}" and getting new
              predictions...
            </span>
          </p>
        </div>

        <!-- Predictions table -->
        <div class="overflow-hidden">
          <table class="w-full">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200">
                <th
                  class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Rank
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Word (Click to Continue)
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Probability
                </th>
                <th
                  class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Token ID
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr
                v-for="(prediction, index) in predictions"
                :key="prediction.tokenId"
                class="hover:bg-gray-50"
              >
                <td class="px-4 py-3 text-sm text-gray-900">
                  {{ index + 1 }}
                </td>
                <td class="px-4 py-3 text-sm font-medium text-gray-900">
                  <button
                    @click="continueWithPrediction(prediction.word)"
                    :disabled="
                      isLoading || continuingWithWord !== '' || isRateLimited
                    "
                    class="px-3 py-1 rounded-md bg-blue-50 hover:bg-blue-100 text-blue-800 border border-blue-200 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                    :class="{
                      'animate-pulse': continuingWithWord === prediction.word,
                    }"
                    :title="
                      isRateLimited
                        ? 'Rate limited - please wait'
                        : `Click to add '${prediction.word}' to your phrase`
                    "
                  >
                    <span v-if="continuingWithWord === prediction.word"
                      >⏳ Adding...</span
                    >
                    <span v-else>{{ prediction.word }}</span>
                  </button>
                </td>
                <td class="px-4 py-3 text-sm text-gray-600">
                  <div class="flex items-center space-x-2">
                    <span>{{ formatPercentage(prediction.probability) }}</span>
                    <div class="flex-1 bg-gray-200 rounded-full h-2 max-w-24">
                      <div
                        class="bg-blue-600 h-2 rounded-full"
                        :style="`width: ${prediction.probability * 100}%`"
                      ></div>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">
                  {{ prediction.tokenId }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="card text-center">
        <div
          class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"
        ></div>
        <p class="text-gray-600">Running AI prediction...</p>
        <p class="text-gray-500 text-sm mt-2">
          This may take a moment for the first request
        </p>
      </div>
    </div>
  </div>
</template>
