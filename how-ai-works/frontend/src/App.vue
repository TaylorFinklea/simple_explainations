<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { API_CONFIG } from './config'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const connectionStatus = ref<'checking' | 'connected' | 'disconnected'>('checking')
const showServerDetails = ref(false)

const checkServerConnection = async () => {
  connectionStatus.value = 'checking'
  try {
    const response = await fetch(API_CONFIG.healthEndpoint)
    if (response.ok) {
      connectionStatus.value = 'connected'
    } else {
      connectionStatus.value = 'disconnected'
    }
  } catch (err) {
    console.error('Server connection failed:', err)
    connectionStatus.value = 'disconnected'
  }
}

const toggleServerDetails = () => {
  showServerDetails.value = !showServerDetails.value
}

const navigateTo = (name: string) => {
  router.push({ name })
}

// Check connection on component mount
onMounted(() => {
  checkServerConnection()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Navigation Bar -->
    <nav class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-4xl mx-auto px-4">
        <div class="flex justify-between items-center h-16">
          <!-- Logo/Title -->
          <div class="flex items-center space-x-4">
            <h1 class="text-xl font-bold text-gray-900">
              AI Word Prediction Demo
            </h1>
          </div>

          <!-- Navigation Links -->
          <div class="flex space-x-1">
            <button
              @click="navigateTo('WordPrediction')"
              :class="{
                'bg-blue-100 text-blue-700': route.name === 'WordPrediction',
                'text-gray-600 hover:text-gray-900 hover:bg-gray-100': route.name !== 'WordPrediction'
              }"
              class="px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200"
            >
              Word Prediction
            </button>
            <button
              @click="navigateTo('StreamingSimulation')"
              :class="{
                'bg-blue-100 text-blue-700': route.name === 'StreamingSimulation',
                'text-gray-600 hover:text-gray-900 hover:bg-gray-100': route.name !== 'StreamingSimulation'
              }"
              class="px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200"
            >
              AI Streaming
            </button>
          </div>

          <!-- Server Status -->
          <div class="flex items-center space-x-2">
            <div v-if="connectionStatus === 'checking'" class="flex items-center space-x-2 text-yellow-600">
              <div class="animate-spin rounded-full h-3 w-3 border-b-2 border-yellow-600"></div>
              <span class="text-xs">Checking...</span>
            </div>
            <div v-else-if="connectionStatus === 'connected'" class="flex items-center space-x-2 text-green-600">
              <div class="w-2 h-2 bg-green-600 rounded-full"></div>
              <button 
                @click="toggleServerDetails"
                class="text-xs hover:underline focus:outline-none"
              >
                Connected
              </button>
            </div>
            <div v-else class="flex items-center space-x-2 text-red-600">
              <div class="w-2 h-2 bg-red-600 rounded-full"></div>
              <button 
                @click="checkServerConnection"
                class="text-xs hover:underline focus:outline-none"
                title="Click to retry connection"
              >
                Disconnected
              </button>
            </div>
          </div>
        </div>

        <!-- Server Details (collapsible) -->
        <div v-if="connectionStatus === 'connected' && showServerDetails" class="pb-4">
          <div class="bg-green-50 border border-green-200 rounded-lg p-3">
            <div class="flex items-center space-x-2">
              <div class="w-2 h-2 bg-green-600 rounded-full"></div>
              <span class="text-green-800 font-medium text-sm">AI Model Ready</span>
            </div>
            <p class="text-green-700 text-xs mt-1">
              Connected to FastAPI backend running HuggingFace SmolLM2-1.7B
            </p>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="py-8">
      <router-view />
    </main>
  </div>
</template>