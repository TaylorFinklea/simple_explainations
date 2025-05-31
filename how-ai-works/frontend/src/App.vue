<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface PredictionResult {
  word: string
  probability: number
  tokenId: number
}

const inputPhrase = ref('The capital of France is')
const topKTokens = ref(5)
const predictions = ref<PredictionResult[]>([])
const isLoading = ref(false)
const error = ref('')
const connectionStatus = ref<'checking' | 'connected' | 'disconnected'>('checking')

const runPrediction = async () => {
  if (!inputPhrase.value.trim()) {
    error.value = 'Please enter a phrase'
    return
  }

  isLoading.value = true
  error.value = ''
  predictions.value = []

  try {
    const response = await fetch('http://localhost:8000/predict', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input_phrase: inputPhrase.value,
        top_k_tokens: topKTokens.value
      })
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
    }

    const result = await response.json()
    predictions.value = result.predictions.map(pred => ({
      word: pred.word,
      probability: pred.probability,
      tokenId: pred.token_id
    }))

  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      error.value = 'Cannot connect to AI server. Make sure the backend is running on http://localhost:8000'
      connectionStatus.value = 'disconnected'
    } else {
      error.value = `Failed to get predictions: ${err.message}`
    }
    console.error('Prediction error:', err)
  } finally {
    isLoading.value = false
  }
}

const formatPercentage = (probability: number) => {
  return (probability * 100).toFixed(1) + '%'
}

const checkServerConnection = async () => {
  connectionStatus.value = 'checking'
  try {
    const response = await fetch('http://localhost:8000/health')
    if (response.ok) {
      connectionStatus.value = 'connected'
    } else {
      connectionStatus.value = 'disconnected'
    }
  } catch (err) {
    connectionStatus.value = 'disconnected'
  }
}

// Check connection on component mount
onMounted(() => {
  checkServerConnection()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-4xl mx-auto px-4">
      <!-- Header -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">
          AI Word Prediction Demo
        </h1>
        <p class="text-gray-600">
          Enter a phrase and see what the AI thinks comes next
        </p>
        
        <!-- Connection Status -->
        <div class="mt-4">
          <div v-if="connectionStatus === 'checking'" class="flex items-center justify-center space-x-2 text-yellow-600">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-yellow-600"></div>
            <span class="text-sm">Checking server connection...</span>
          </div>
          <div v-else-if="connectionStatus === 'connected'" class="flex items-center justify-center space-x-2 text-green-600">
            <div class="w-3 h-3 bg-green-600 rounded-full"></div>
            <span class="text-sm">Server connected</span>
          </div>
          <div v-else class="flex items-center justify-center space-x-2 text-red-600">
            <div class="w-3 h-3 bg-red-600 rounded-full"></div>
            <span class="text-sm">Server disconnected - Start the backend with: uv run ai-server</span>
            <button @click="checkServerConnection" class="ml-2 text-xs underline hover:no-underline">
              Retry
            </button>
          </div>
        </div>
      </div>

      <!-- Server Status Card -->
      <div v-if="connectionStatus === 'connected'" class="card mb-6 bg-green-50 border-green-200">
        <div class="flex items-center space-x-2">
          <div class="w-3 h-3 bg-green-600 rounded-full"></div>
          <span class="text-green-800 font-medium">AI Model Ready</span>
        </div>
        <p class="text-green-700 text-sm mt-1">
          Connected to FastAPI backend running HuggingFace SmolLM2-1.7B
        </p>
      </div>
      
      <div v-else-if="connectionStatus === 'disconnected'" class="card mb-6 bg-red-50 border-red-200">
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

      <!-- Input Section -->
      <div class="card mb-8">
        <div class="space-y-4">
          <div>
            <label for="phrase" class="block text-sm font-medium text-gray-700 mb-2">
              Input Phrase
            </label>
            <input
              id="phrase"
              v-model="inputPhrase"
              type="text"
              class="input-field"
              placeholder="Enter a phrase..."
              @keyup.enter="runPrediction"
              :disabled="connectionStatus !== 'connected'"
            />
          </div>

          <div>
            <label for="topK" class="block text-sm font-medium text-gray-700 mb-2">
              Number of Predictions
            </label>
            <input
              id="topK"
              v-model.number="topKTokens"
              type="number"
              min="1"
              max="10"
              class="input-field w-32"
              :disabled="connectionStatus !== 'connected'"
            />
          </div>

          <button
            @click="runPrediction"
            :disabled="isLoading || connectionStatus !== 'connected'"
            class="btn-primary"
          >
            <span v-if="isLoading">Predicting...</span>
            <span v-else-if="connectionStatus !== 'connected'">Server Disconnected</span>
            <span v-else>Predict Next Word</span>
          </button>
        </div>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
        <div class="flex">
          <div class="text-red-600 text-sm">{{ error }}</div>
        </div>
      </div>

      <!-- Results Section -->
      <div v-if="predictions.length > 0" class="card">
        <h2 class="text-xl font-semibold text-gray-900 mb-4">
          Predictions
        </h2>
        
        <!-- Complete sentence preview -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div class="text-sm font-medium text-blue-900 mb-1">
            Complete sentence with top prediction:
          </div>
          <div class="text-blue-800">
            "{{ inputPhrase }} {{ predictions[0]?.word }}"
          </div>
        </div>

        <!-- Predictions table -->
        <div class="overflow-hidden">
          <table class="w-full">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200">
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rank
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Word
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Probability
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
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
                  {{ prediction.word }}
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
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p class="text-gray-600">Running AI prediction...</p>
        <p class="text-gray-500 text-sm mt-2">This may take a moment for the first request</p>
      </div>
    </div>
  </div>
</template>