<script setup lang="ts">
import { ref, onMounted } from "vue";
import { API_CONFIG } from "../config";

interface PredictionResult {
  word: string;
  probability: number;
  tokenId: number;
}

interface StreamingStep {
  step: number;
  phrase: string;
  predictions: PredictionResult[];
  selectedWord: string;
  timestamp: Date;
  round: number;
}

const inputPhrase = ref("The wheels on the bus go");
const waitDuration = ref(2);
const temperature = ref(1.0);
const topK = ref(5);
const numWords = ref(3);

const isStreaming = ref(false);
const isPaused = ref(false);
const connectionStatus = ref<"checking" | "connected" | "disconnected">(
  "checking",
);
const modelStatus = ref<'not_loaded' | 'loading' | 'loaded' | 'error'>('not_loaded');
const isLoadingModel = ref(false);
const currentStep = ref(0);
const currentRound = ref(1);
const streamingHistory = ref<StreamingStep[]>([]);
const currentPhrase = ref("");
const currentPredictions = ref<PredictionResult[]>([]);
const timeRemaining = ref(0);
const isCompleted = ref(false);
const isHistoryCollapsed = ref(true);

let streamingInterval: number | null = null;
let countdownInterval: number | null = null;

const formatPercentage = (probability: number) => {
  return (probability * 100).toFixed(1) + "%";
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
  } catch (err) {
    console.error("Server connection failed:", err);
    connectionStatus.value = "disconnected";
  }
};

const checkModelStatus = async () => {
  try {
    const response = await fetch(API_CONFIG.modelStatusEndpoint);
    if (response.ok) {
      const data = await response.json();
      modelStatus.value = data.status;
      return data.status;
    }
  } catch (err) {
    console.error('Model status check failed:', err);
  }
  return 'error';
};

const loadModel = async () => {
  isLoadingModel.value = true;
  
  try {
    const response = await fetch(API_CONFIG.modelLoadEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (response.ok) {
      const data = await response.json();
      if (data.status === 'success' || data.status === 'already_loaded') {
        modelStatus.value = 'loaded';
      } else if (data.status === 'already_loading') {
        modelStatus.value = 'loading';
        // Poll for completion
        await pollModelStatus();
      }
    } else {
      modelStatus.value = 'error';
    }
  } catch (err) {
    modelStatus.value = 'error';
    console.error('Model loading error:', err);
  } finally {
    isLoadingModel.value = false;
  }
};

const pollModelStatus = async () => {
  const maxAttempts = 60; // 2 minutes with 2-second intervals
  let attempts = 0;
  
  const poll = async () => {
    if (attempts >= maxAttempts) {
      modelStatus.value = 'error';
      return;
    }
    
    const status = await checkModelStatus();
    if (status === 'loaded') {
      return;
    } else if (status === 'error') {
      return;
    } else if (status === 'loading') {
      attempts++;
      setTimeout(poll, 2000); // Check again in 2 seconds
    }
  };
  
  await poll();
};

const getPredictions = async (phrase: string) => {
  try {
    const response = await fetch(API_CONFIG.predictEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        input_phrase: phrase,
        top_k_tokens: topK.value,
        temperature: temperature.value,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result.predictions
      .map((pred: any) => ({
        word: pred.word,
        probability: pred.probability,
        tokenId: pred.token_id,
      }))
      .filter(
        (pred: PredictionResult) => pred.word && pred.word.trim().length > 0,
      );
  } catch (err) {
    console.error("Prediction error:", err);
    return [];
  }
};

const selectWordByProbability = (predictions: PredictionResult[]) => {
  if (predictions.length === 0) return null;

  // Filter out any empty or whitespace-only words
  const validPredictions = predictions.filter(
    (pred) => pred.word && pred.word.trim().length > 0,
  );
  if (validPredictions.length === 0) return null;

  // For simulation, we'll use a weighted random selection based on probability
  const random = Math.random();
  let cumulativeProbability = 0;

  for (const prediction of validPredictions) {
    cumulativeProbability += prediction.probability;
    if (random <= cumulativeProbability) {
      return prediction;
    }
  }

  // Fallback to highest probability
  return validPredictions[0];
};

const startCountdown = () => {
  timeRemaining.value = waitDuration.value;
  countdownInterval = setInterval(() => {
    timeRemaining.value--;
    if (timeRemaining.value <= 0 && countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  }, 1000);
};

const streamNextWord = async () => {
  if (currentStep.value >= numWords.value) {
    completeStreaming();
    return;
  }

  // Get predictions for current phrase
  const predictions = await getPredictions(currentPhrase.value);
  if (predictions.length === 0) {
    console.warn("No valid predictions received, stopping streaming");
    stopStreaming();
    return;
  }

  currentPredictions.value = predictions;

  // Start countdown
  startCountdown();

  // Wait for the specified duration
  await new Promise((resolve) =>
    setTimeout(resolve, waitDuration.value * 1000),
  );

  if (!isStreaming.value) return; // Check if streaming was stopped

  // Select next word
  const selectedPrediction = selectWordByProbability(predictions);
  if (!selectedPrediction || !selectedPrediction.word.trim()) {
    console.warn("No valid word selected, stopping streaming");
    stopStreaming();
    return;
  }

  // Add to history
  streamingHistory.value.push({
    step: currentStep.value + 1,
    phrase: currentPhrase.value,
    predictions: [...predictions],
    selectedWord: selectedPrediction.word,
    timestamp: new Date(),
    round: currentRound.value,
  });

  // Update current phrase with proper spacing
  const trimmedWord = selectedPrediction.word.trim();
  if (trimmedWord) {
    currentPhrase.value = `${currentPhrase.value} ${trimmedWord}`.trim();
    currentStep.value++;
  } else {
    // If word is empty after trimming, stop streaming
    console.warn("Selected word is empty after trimming, stopping streaming");
    stopStreaming();
    return;
  }

  // Clear current predictions for next iteration
  currentPredictions.value = [];
};

const startStreaming = async () => {
  if (connectionStatus.value !== "connected" || modelStatus.value !== "loaded") return;
  
  // Check model status first
  const currentModelStatus = await checkModelStatus();
  if (currentModelStatus !== 'loaded') {
    return;
  }

  isStreaming.value = true;
  isPaused.value = false;
  currentStep.value = 0;
  currentRound.value = 1;
  streamingHistory.value = [];
  currentPhrase.value = inputPhrase.value;
  currentPredictions.value = [];
  isCompleted.value = false;

  // Start streaming loop
  while (isStreaming.value && currentStep.value < numWords.value) {
    if (!isPaused.value) {
      await streamNextWord();
    } else {
      await new Promise((resolve) => setTimeout(resolve, 100)); // Small delay when paused
    }
  }

  // Check if we completed naturally (not stopped manually)
  if (isStreaming.value && currentStep.value >= numWords.value) {
    completeStreaming();
  }
};

const completeStreaming = () => {
  isStreaming.value = false;
  isPaused.value = false;
  currentPredictions.value = [];
  timeRemaining.value = 0;
  isCompleted.value = true;

  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
};

const stopStreaming = () => {
  isStreaming.value = false;
  isPaused.value = false;
  currentPredictions.value = [];
  timeRemaining.value = 0;
  isCompleted.value = false;

  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
};

const pauseStreaming = () => {
  isPaused.value = !isPaused.value;
  if (isPaused.value && countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
};

const resetSimulation = () => {
  stopStreaming();
  streamingHistory.value = [];
  currentPhrase.value = "";
  currentStep.value = 0;
  currentRound.value = 1;
};

const continueStreaming = async () => {
  if (connectionStatus.value !== "connected" || modelStatus.value !== "loaded") return;
  
  // Check model status first
  const currentModelStatus = await checkModelStatus();
  if (currentModelStatus !== 'loaded') {
    return;
  }

  // Reset completion state but keep history and current phrase
  isCompleted.value = false;
  currentStep.value = 0;
  currentRound.value += 1;
  currentPredictions.value = [];

  // Start streaming from current phrase
  isStreaming.value = true;
  isPaused.value = false;

  // Continue streaming loop for another round
  while (isStreaming.value && currentStep.value < numWords.value) {
    if (!isPaused.value) {
      await streamNextWord();
    } else {
      await new Promise((resolve) => setTimeout(resolve, 100)); // Small delay when paused
    }
  }

  // Check if we completed naturally (not stopped manually)
  if (isStreaming.value && currentStep.value >= numWords.value) {
    completeStreaming();
  }
};

// Check connection on component mount
onMounted(() => {
  checkServerConnection();
});
</script>

<template>
  <div class="max-w-6xl mx-auto px-4">
    <!-- Page Header -->
    <div class="text-center mb-8">
      <h2 class="text-2xl font-bold text-gray-900 mb-2">
        AI Streaming Simulation
      </h2>
      <p class="text-gray-600">
        Watch the AI build sentences word by word with configurable parameters
      </p>
    </div>

    <!-- Server Status -->
    <div
      v-if="connectionStatus === 'disconnected'"
      class="card mb-6 bg-red-50 border-red-200"
    >
      <div class="flex items-center space-x-2">
        <div class="w-3 h-3 bg-red-600 rounded-full"></div>
        <span class="text-red-800 font-medium">Backend Server Not Running</span>
      </div>
      <p class="text-red-700 text-sm mt-1 mb-3">
        Please start the FastAPI server to use the AI streaming simulation.
      </p>
      <div class="bg-gray-100 p-2 rounded text-sm">
        <code>cd how-ai-works && uv run ai-server</code>
      </div>
    </div>

    <!-- Model Loading Status Card -->
    <div v-if="connectionStatus === 'connected' && modelStatus !== 'loaded'" class="card mb-6">
      <!-- Model Not Loaded -->
      <div v-if="modelStatus === 'not_loaded'" class="bg-yellow-50 border-yellow-200 p-4 rounded-lg">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center space-x-2">
              <div class="w-3 h-3 bg-yellow-600 rounded-full"></div>
              <span class="text-yellow-800 font-medium">AI Model Not Loaded</span>
            </div>
            <p class="text-yellow-700 text-sm mt-1">
              The AI model needs to be loaded before you can start streaming. This is a one-time process.
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
      <div v-else-if="modelStatus === 'loading' || isLoadingModel" class="bg-blue-50 border-blue-200 p-4 rounded-lg">
        <div class="flex items-center space-x-3">
          <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <div>
            <div class="text-blue-800 font-medium">Loading AI Model...</div>
            <p class="text-blue-700 text-sm mt-1">
              This may take 1-2 minutes for the first time. The model (SmolLM2-1.7B) is being downloaded and initialized.
            </p>
            <div class="mt-2 text-xs text-blue-600">
              ⏳ Please wait, do not refresh the page
            </div>
          </div>
        </div>
      </div>

      <!-- Model Error -->
      <div v-else-if="modelStatus === 'error'" class="bg-red-50 border-red-200 p-4 rounded-lg">
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

    <!-- Model Ready Confirmation -->
    <div v-if="connectionStatus === 'connected' && modelStatus === 'loaded'" class="card mb-6 bg-green-50 border-green-200">
      <div class="flex items-center space-x-2">
        <div class="w-3 h-3 bg-green-600 rounded-full"></div>
        <span class="text-green-800 font-medium">AI Model Ready</span>
      </div>
      <p class="text-green-700 text-sm mt-1">
        🎉 SmolLM2-1.7B is loaded and ready for streaming!
      </p>
    </div>

    <!-- Configuration Panel -->
    <div class="card mb-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Configuration</h3>

      <!-- Info about token filtering -->
      <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
        <p class="text-blue-800 text-sm">
          <strong>Note:</strong> Empty or whitespace-only tokens are
          automatically filtered out during streaming. If no valid words are
          available, the streaming will stop early.
        </p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <!-- Starting Phrase -->
        <div class="col-span-full">
          <label
            for="phrase"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Starting Phrase
          </label>
          <input
            id="phrase"
            v-model="inputPhrase"
            type="text"
            class="input-field"
            placeholder="Enter starting phrase..."
            :disabled="isStreaming || modelStatus !== 'loaded'"
          />
        </div>

        <!-- Wait Duration -->
        <div>
          <label
            for="wait"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Wait Duration (seconds)
          </label>
          <input
            id="wait"
            v-model.number="waitDuration"
            type="number"
            min="0.5"
            max="10"
            step="0.5"
            class="input-field"
            :disabled="isStreaming || modelStatus !== 'loaded'"
          />
        </div>

        <!-- Temperature -->
        <div>
          <label
            for="temperature"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Temperature
          </label>
          <input
            id="temperature"
            v-model.number="temperature"
            type="number"
            min="0.1"
            max="2.0"
            step="0.1"
            class="input-field"
            :disabled="isStreaming || modelStatus !== 'loaded'"
          />
        </div>

        <!-- Top K -->
        <div>
          <label
            for="topk"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Number of Predictions
          </label>
          <input
            id="topk"
            v-model.number="topK"
            type="number"
            min="1"
            max="20"
            class="input-field"
            :disabled="isStreaming || modelStatus !== 'loaded'"
          />
        </div>

        <!-- Number of Words -->
        <div>
          <label
            for="numwords"
            class="block text-sm font-medium text-gray-700 mb-2"
          >
            Words to Generate
          </label>
          <input
            id="numwords"
            v-model.number="numWords"
            type="number"
            min="1"
            max="20"
            class="input-field"
            :disabled="isStreaming || modelStatus !== 'loaded'"
          />
        </div>
      </div>

      <!-- Control Buttons -->
      <div class="flex space-x-2">
        <!-- Primary Action Button (Start or Continue) -->
        <button
          v-if="!isCompleted"
          @click="startStreaming"
          :disabled="isStreaming || connectionStatus !== 'connected' || modelStatus !== 'loaded'"
          class="btn-primary"
        >
          <span v-if="connectionStatus !== 'connected'">Server Disconnected</span>
          <span v-else-if="modelStatus === 'loading'">Model Loading...</span>
          <span v-else-if="modelStatus === 'not_loaded'">Load Model First</span>
          <span v-else-if="modelStatus === 'error'">Model Error</span>
          <span v-else>Start Streaming</span>
        </button>

        <button
          v-if="isCompleted"
          @click="continueStreaming"
          :disabled="isStreaming || connectionStatus !== 'connected' || modelStatus !== 'loaded'"
          class="btn-primary"
        >
          <span v-if="connectionStatus !== 'connected'">Server Disconnected</span>
          <span v-else-if="modelStatus === 'loading'">Model Loading...</span>
          <span v-else-if="modelStatus === 'not_loaded'">Load Model First</span>
          <span v-else-if="modelStatus === 'error'">Model Error</span>
          <span v-else>Continue</span>
        </button>

        <!-- Secondary Control Buttons -->
        <button
          @click="pauseStreaming"
          :disabled="!isStreaming"
          class="btn-secondary"
        >
          {{ isPaused ? "Resume" : "Pause" }}
        </button>

        <button
          @click="stopStreaming"
          :disabled="!isStreaming"
          class="btn-secondary"
        >
          Stop
        </button>

        <button
          @click="resetSimulation"
          :disabled="isStreaming"
          class="btn-secondary"
        >
          Reset
        </button>
      </div>
    </div>

    <!-- Current Status -->
    <div v-if="isStreaming || streamingHistory.length > 0" class="card mb-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Current Status</h3>

      <!-- Progress -->
      <div class="mb-4">
        <div class="flex justify-between text-sm text-gray-600 mb-2">
          <span
            >Round {{ currentRound }} - Progress: {{ currentStep }} /
            {{ numWords }} words</span
          >
          <span v-if="isStreaming && !isPaused && timeRemaining > 0">
            Next word in: {{ timeRemaining }}s
          </span>
          <span v-else-if="isPaused" class="text-yellow-600">⏸️ Paused</span>
          <span v-else-if="isCompleted" class="text-green-600"
            >✅ Complete - Click "Continue" to generate more</span
          >
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div
            class="bg-blue-600 h-2 rounded-full transition-all duration-300"
            :style="`width: ${(currentStep / numWords) * 100}%`"
          ></div>
        </div>
      </div>

      <!-- Current Phrase -->
      <div
        class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4"
        :class="{ 'bg-green-50 border-green-200': isCompleted }"
      >
        <div
          class="text-sm font-medium mb-2"
          :class="{
            'text-blue-900': !isCompleted,
            'text-green-900': isCompleted,
          }"
        >
          Current Phrase:
          <span v-if="isCompleted" class="text-green-600 ml-2"
            >✅ Generation Complete</span
          >
        </div>
        <div
          class="text-lg"
          :class="{
            'text-blue-800': !isCompleted,
            'text-green-800': isCompleted,
          }"
        >
          "{{ currentPhrase || inputPhrase }}"
        </div>
        <div v-if="isCompleted" class="text-sm text-green-700 mt-2">
          Click "Continue" to add {{ numWords }} more words to this phrase
        </div>
      </div>

      <!-- Current Predictions (if active) -->
      <div v-if="currentPredictions.length > 0" class="mb-4">
        <div class="text-sm font-medium text-gray-700 mb-2">
          Current Predictions (selecting in {{ timeRemaining }}s):
        </div>
        <div class="overflow-hidden rounded-lg border border-gray-200">
          <table class="w-full">
            <thead class="bg-gray-50">
              <tr>
                <th
                  class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                >
                  Rank
                </th>
                <th
                  class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                >
                  Word
                </th>
                <th
                  class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                >
                  Probability
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr
                v-for="(prediction, index) in currentPredictions"
                :key="prediction.tokenId"
              >
                <td class="px-4 py-2 text-sm text-gray-900">{{ index + 1 }}</td>
                <td class="px-4 py-2 text-sm font-medium text-gray-900">
                  {{ prediction.word }}
                </td>
                <td class="px-4 py-2 text-sm text-gray-600">
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
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Streaming History -->
    <div v-if="streamingHistory.length > 0" class="card">
      <div
        class="flex justify-between items-center mb-4 cursor-pointer hover:bg-gray-50 -m-4 p-4 rounded-lg"
        @click="isHistoryCollapsed = !isHistoryCollapsed"
      >
        <div class="flex items-center space-x-2">
          <h3 class="text-lg font-semibold text-gray-900">Streaming History</h3>
          <svg
            class="w-5 h-5 text-gray-500 transition-transform duration-200"
            :class="{ 'rotate-180': !isHistoryCollapsed }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 9l-7 7-7-7"
            ></path>
          </svg>
        </div>
        <span class="text-sm text-gray-500"
          >{{ streamingHistory.length }} step{{
            streamingHistory.length !== 1 ? "s" : ""
          }}
          completed</span
        >
      </div>

      <div v-if="!isHistoryCollapsed" class="space-y-4">
        <div
          v-for="step in streamingHistory"
          :key="`${step.round}-${step.step}`"
          class="border border-gray-200 rounded-lg p-4"
        >
          <div class="flex justify-between items-start mb-3">
            <div class="flex items-center space-x-2">
              <span
                class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs font-medium"
              >
                Round {{ step.round }}
              </span>
              <span
                class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium"
              >
                Step {{ step.step }}
              </span>
              <span class="text-xs text-gray-500">
                {{ step.timestamp.toLocaleTimeString() }}
              </span>
            </div>
            <div class="text-sm">
              <span class="text-gray-600">Selected:</span>
              <span class="font-medium text-blue-600 ml-1">{{
                step.selectedWord
              }}</span>
            </div>
          </div>

          <div class="text-sm text-gray-600 mb-3">
            Starting phrase: "{{ step.phrase }}"
          </div>

          <!-- Predictions for this step -->
          <div class="overflow-hidden rounded border border-gray-200">
            <table class="w-full text-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th
                    class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    Rank
                  </th>
                  <th
                    class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    Word
                  </th>
                  <th
                    class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                  >
                    Probability
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr
                  v-for="(prediction, index) in step.predictions"
                  :key="prediction.tokenId"
                  :class="{
                    'bg-green-50': prediction.word === step.selectedWord,
                  }"
                >
                  <td class="px-3 py-2 text-gray-900">{{ index + 1 }}</td>
                  <td class="px-3 py-2 font-medium text-gray-900">
                    <span
                      :class="{
                        'text-green-700 font-bold':
                          prediction.word === step.selectedWord,
                      }"
                    >
                      {{ prediction.word }}
                    </span>
                    <span
                      v-if="prediction.word === step.selectedWord"
                      class="ml-1 text-green-600"
                      >✓</span
                    >
                  </td>
                  <td class="px-3 py-2 text-gray-600">
                    {{ formatPercentage(prediction.probability) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
