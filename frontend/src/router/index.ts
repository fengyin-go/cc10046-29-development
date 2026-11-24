import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import RevalidationView from '@/views/RevalidationView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/field_revalidation', name: 'field_revalidation', component: RevalidationView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
