<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useProjectsStore } from '@/stores/projects'
import { useAuthStore } from '@/stores/auth'
import type { Project, ProjectStatus } from '@/api/projects'

const { t, locale } = useI18n()
const router = useRouter()
const projects = useProjectsStore()
const auth = useAuthStore()

onMounted(() => {
  projects.fetchAll()
})

const stats = computed(() => [
  {
    label: t('dashboard.statTotal'),
    value: projects.count,
    tone: 'neutral' as const,
  },
  {
    label: t('dashboard.statDrafting'),
    value: projects.drafting.length,
    tone: 'warning' as const,
  },
  {
    label: t('dashboard.statTraining'),
    value: projects.training.length,
    tone: 'info' as const,
  },
  {
    label: t('dashboard.statDeployed'),
    value: projects.deployed.length,
    tone: 'success' as const,
  },
])

const toneClass: Record<'neutral' | 'warning' | 'info' | 'success', string> = {
  neutral: 'text-ink-900',
  warning: 'text-warning',
  info: 'text-info',
  success: 'text-success',
}

const statusBadge: Record<ProjectStatus, { bg: string; text: string; key: string }> = {
  drafting: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800', key: 'status.drafting' },
  training: { bg: 'bg-blue-50 border-blue-200', text: 'text-blue-800', key: 'status.training' },
  deployed: {
    bg: 'bg-primary-50 border-primary-200',
    text: 'text-primary-800',
    key: 'status.deployed',
  },
  failed: { bg: 'bg-red-50 border-red-200', text: 'text-red-800', key: 'status.failed' },
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(locale.value, {
      dateStyle: 'medium',
    }).format(new Date(iso))
  } catch {
    return iso.slice(0, 10)
  }
}

const greetingName = computed(() => auth.user?.email?.split('@')[0] ?? '')

async function startNewProject() {
  // Provisional: route to wizard with a placeholder project id placeholder
  // Real flow lands in F3 wizard step 1 (create project) — for now jump straight in
  await router.push({ name: 'wizard', params: { id: 'new' } })
}

function openProject(p: Project) {
  router.push({ name: 'wizard', params: { id: p.id } })
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-[8fr_2fr] gap-6 p-8 max-w-[1440px] mx-auto">
    <!-- 8/10 main column -->
    <section class="space-y-6 min-w-0">
      <header class="flex items-end justify-between gap-4 flex-wrap">
        <div class="space-y-1">
          <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
            {{ t('dashboard.greetingLabel') }}
          </p>
          <h1 class="text-2xl font-semibold text-ink-900">
            {{
              greetingName
                ? t('dashboard.greeting', { name: greetingName })
                : t('dashboard.greetingNoName')
            }}
          </h1>
          <p class="text-sm text-ink-500">{{ t('dashboard.subhead') }}</p>
        </div>
        <AppButton @click="startNewProject">
          + {{ t('dashboard.newProject') }}
        </AppButton>
      </header>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div
          v-for="stat in stats"
          :key="stat.label"
          class="rounded-xl bg-white border border-ink-200 shadow-card p-4"
        >
          <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
            {{ stat.label }}
          </p>
          <p class="mt-1 text-3xl font-semibold font-mono tabular-nums" :class="toneClass[stat.tone]">
            {{ stat.value }}
          </p>
        </div>
      </div>

      <div class="rounded-xl bg-white border border-ink-200 shadow-card">
        <header class="flex items-center justify-between px-5 py-4 border-b border-ink-200">
          <h2 class="text-base font-semibold text-ink-900">{{ t('dashboard.projectsTitle') }}</h2>
          <button
            type="button"
            class="text-xs font-mono text-ink-500 hover:text-ink-900 transition"
            :disabled="projects.loading"
            @click="projects.fetchAll()"
          >
            {{ projects.loading ? t('common.loading') : t('common.refresh') }}
          </button>
        </header>

        <div
          v-if="projects.error"
          class="px-5 py-3 bg-red-50 border-b border-red-100 text-sm text-red-700"
        >
          {{ projects.error }}
        </div>

        <div v-if="!projects.loading && projects.count === 0" class="px-5 py-16 text-center">
          <p class="text-sm text-ink-500">{{ t('dashboard.empty') }}</p>
          <AppButton class="mt-4" @click="startNewProject">
            {{ t('dashboard.emptyCta') }}
          </AppButton>
        </div>

        <table v-else class="w-full">
          <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
            <tr>
              <th class="text-left px-5 py-3 font-medium">{{ t('dashboard.colName') }}</th>
              <th class="text-left px-5 py-3 font-medium">{{ t('dashboard.colSlug') }}</th>
              <th class="text-left px-5 py-3 font-medium">{{ t('dashboard.colStatus') }}</th>
              <th class="text-left px-5 py-3 font-medium">{{ t('dashboard.colUpdated') }}</th>
              <th class="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in projects.items"
              :key="p.id"
              class="border-t border-ink-100 hover:bg-ink-50 cursor-pointer"
              @click="openProject(p)"
            >
              <td class="px-5 py-3.5 text-sm font-medium text-ink-900">{{ p.name }}</td>
              <td class="px-5 py-3.5 text-sm font-mono text-ink-500">{{ p.slug }}</td>
              <td class="px-5 py-3.5">
                <span
                  class="inline-flex items-center h-6 px-2 rounded-full border text-xs font-medium"
                  :class="[statusBadge[p.status].bg, statusBadge[p.status].text]"
                >
                  {{ t(statusBadge[p.status].key) }}
                </span>
              </td>
              <td class="px-5 py-3.5 text-sm text-ink-500 font-mono tabular-nums">
                {{ formatDate(p.updated_at) }}
              </td>
              <td class="px-5 py-3.5 text-right text-ink-400">
                <span class="text-sm">→</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 2/10 sidebar column -->
    <aside class="space-y-4">
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
        <h3 class="text-sm font-semibold text-ink-900">{{ t('dashboard.quickStart') }}</h3>
        <ol class="mt-3 space-y-3 text-sm text-ink-600">
          <li class="flex gap-2">
            <span class="font-mono text-xs text-primary-700 mt-0.5">01</span>
            <span>{{ t('dashboard.qs1') }}</span>
          </li>
          <li class="flex gap-2">
            <span class="font-mono text-xs text-primary-700 mt-0.5">02</span>
            <span>{{ t('dashboard.qs2') }}</span>
          </li>
          <li class="flex gap-2">
            <span class="font-mono text-xs text-primary-700 mt-0.5">03</span>
            <span>{{ t('dashboard.qs3') }}</span>
          </li>
          <li class="flex gap-2">
            <span class="font-mono text-xs text-primary-700 mt-0.5">04</span>
            <span>{{ t('dashboard.qs4') }}</span>
          </li>
        </ol>
      </div>

      <div class="rounded-xl bg-primary-50 border border-primary-200 p-5">
        <h3 class="text-sm font-semibold text-primary-900">{{ t('dashboard.advisorTitle') }}</h3>
        <p class="mt-2 text-sm text-primary-900/80">{{ t('dashboard.advisorBlurb') }}</p>
        <p class="mt-3 text-xs font-mono text-primary-700/80">Gemma 4 · 31b</p>
      </div>

      <div class="rounded-xl border border-ink-200 bg-white p-5">
        <h3 class="text-sm font-semibold text-ink-900">{{ t('dashboard.docsTitle') }}</h3>
        <ul class="mt-3 space-y-2 text-sm text-ink-600">
          <li>· {{ t('dashboard.doc1') }}</li>
          <li>· {{ t('dashboard.doc2') }}</li>
          <li>· {{ t('dashboard.doc3') }}</li>
        </ul>
      </div>
    </aside>
  </div>
</template>
