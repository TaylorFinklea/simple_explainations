import { createRouter, createWebHistory } from 'vue-router'
import WordPrediction from '../views/WordPrediction.vue'
import StreamingSimulation from '../views/StreamingSimulation.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'WordPrediction',
      component: WordPrediction,
      meta: {
        title: 'Word Prediction'
      }
    },
    {
      path: '/streaming',
      name: 'StreamingSimulation',
      component: StreamingSimulation,
      meta: {
        title: 'AI Streaming Simulation'
      }
    }
  ]
})

export default router