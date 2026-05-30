<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useProjectsStore } from '@/stores/projects'
import type { ProjectStatus } from '@/api/projects'
import type { DashboardProject } from '@/api/dashboard'

const { t, locale } = useI18n()
const router = useRouter()
const projects = useProjectsStore()

onMounted(() => {
  projects.fetchSummary()
})

const summary = computed(() => projects.summary)
const stats = computed(() => projects.summary?.stats ?? null)

type Filter = 'all' | 'drafting' | 'training' | 'deployed'
const filter = ref<Filter>('all')
const filterChips: { key: Filter; label: string }[] = [
  { key: 'all', label: 'dashboard.filterAll' },
  { key: 'drafting', label: 'dashboard.filterDrafting' },
  { key: 'training', label: 'dashboard.filterTraining' },
  { key: 'deployed', label: 'dashboard.filterDeployed' },
]

const allProjects = computed<DashboardProject[]>(() => projects.summary?.projects ?? [])
const filteredProjects = computed(() =>
  filter.value === 'all'
    ? allProjects.value
    : allProjects.value.filter((p) => p.status === filter.value),
)
const featured = computed<DashboardProject | null>(() => filteredProjects.value[0] ?? null)
const restProjects = computed(() => filteredProjects.value.slice(1))

const isEmpty = computed(
  () => !projects.summaryLoading && summary.value !== null && allProjects.value.length === 0,
)

// Per-project mAP renders as a percentage (Figma parity); the aggregate AVG.
// mAP stat keeps three-decimal form. Null until a succeeded train run exists.
function formatPct(v: number | null): string {
  return v == null ? t('dashboard.noMetric') : `${(v * 100).toFixed(1)}%`
}
function formatMap(v: number | null | undefined): string {
  return v == null ? t('dashboard.noMetric') : v.toFixed(3)
}

function relTime(iso: string | null): string {
  if (!iso) return ''
  const sec = Math.round((new Date(iso).getTime() - Date.now()) / 1000)
  const rtf = new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' })
  const abs = Math.abs(sec)
  if (abs < 60) return rtf.format(sec, 'second')
  const min = Math.round(sec / 60)
  if (Math.abs(min) < 60) return rtf.format(min, 'minute')
  const hr = Math.round(sec / 3600)
  if (Math.abs(hr) < 24) return rtf.format(hr, 'hour')
  return rtf.format(Math.round(sec / 86400), 'day')
}

const statusBadge: Record<ProjectStatus, { dot: string; text: string; bg: string; key: string }> = {
  drafting: { dot: 'bg-ink-400', text: 'text-ink-700', bg: 'bg-ink-100', key: 'status.drafting' },
  training: { dot: 'bg-info', text: 'text-info', bg: 'bg-blue-50', key: 'status.training' },
  deployed: {
    dot: 'bg-primary-500',
    text: 'text-primary-800',
    bg: 'bg-primary-50',
    key: 'status.deployed',
  },
  failed: { dot: 'bg-danger', text: 'text-red-700', bg: 'bg-red-50', key: 'status.failed' },
}

async function startNewProject() {
  await router.push({ name: 'wizard', params: { id: 'new' } })
}
function openProject(p: DashboardProject) {
  router.push({ name: 'wizard', params: { id: p.id } })
}
</script>

<template>
  <div class="p-8 max-w-[1320px] mx-auto space-y-8">
    <!-- Top action row — the shell top bar has no New Project affordance yet -->
    <div class="flex items-center justify-end">
      <AppButton data-testid="dashboard-new-project" @click="startNewProject">
        + {{ t('dashboard.newProject') }}
      </AppButton>
    </div>

    <!-- Stat cards — every value traces to a real row; no trend deltas. -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        data-testid="dashboard-stat-active"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('dashboard.statActive') }}
        </p>
        <p class="mt-2 text-3xl font-semibold font-mono tabular-nums text-ink-900">
          {{ stats?.active_projects ?? '—' }}
        </p>
      </div>

      <div
        data-testid="dashboard-stat-models"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('dashboard.statModels') }}
        </p>
        <p class="mt-2 text-3xl font-semibold font-mono tabular-nums text-ink-900">
          {{ stats?.models_deployed ?? '—' }}
        </p>
      </div>

      <div
        data-testid="dashboard-stat-edges"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('dashboard.statEdges') }}
        </p>
        <p class="mt-2 text-3xl font-semibold font-mono tabular-nums text-ink-900">
          <template v-if="stats">
            {{ t('dashboard.edgesOf', { online: stats.edges_online, total: stats.edges_total }) }}
          </template>
          <template v-else>—</template>
        </p>
      </div>

      <div
        data-testid="dashboard-stat-map"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('dashboard.statMap') }}
        </p>
        <p class="mt-2 text-3xl font-semibold font-mono tabular-nums text-ink-900">
          {{ formatMap(stats?.avg_map) }}
        </p>
      </div>
    </div>

    <!-- All projects -->
    <section class="space-y-5">
      <header class="flex items-end justify-between gap-4 flex-wrap">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-ink-900">{{ t('dashboard.allProjects') }}</h2>
          <p class="text-sm text-ink-500">{{ t('dashboard.allProjectsSub') }}</p>
        </div>
        <div class="inline-flex items-center gap-1.5">
          <button
            v-for="chip in filterChips"
            :key="chip.key"
            type="button"
            :data-testid="`dashboard-filter-${chip.key}`"
            class="h-8 px-3 rounded-full text-xs font-medium border transition"
            :class="
              filter === chip.key
                ? 'border-primary-200 bg-primary-50 text-primary-800'
                : 'border-border-default bg-white text-ink-500 hover:text-ink-900'
            "
            :aria-pressed="filter === chip.key"
            @click="filter = chip.key"
          >
            {{ t(chip.label) }}
          </button>
        </div>
      </header>

      <div
        v-if="projects.error"
        class="rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700"
      >
        {{ projects.error }}
      </div>

      <div
        v-else-if="projects.summaryLoading && !summary"
        class="rounded-xl border border-border-default bg-white px-5 py-16 text-center text-sm text-ink-500"
      >
        {{ t('common.loading') }}
      </div>

      <!-- Empty state (Figma 8:231) -->
      <div
        v-else-if="isEmpty"
        data-testid="dashboard-empty"
        class="rounded-2xl border border-border-default bg-white px-6 py-16 text-center max-w-2xl mx-auto"
      >
        <div
          class="mx-auto h-16 w-16 rounded-2xl bg-primary-50 border border-primary-100 flex items-center justify-center"
        >
          <span class="block h-7 w-9 rounded-sm border-2 border-primary-500" />
        </div>
        <h3 class="mt-6 text-xl font-semibold text-ink-900">{{ t('dashboard.emptyTitle') }}</h3>
        <p class="mt-3 text-sm text-ink-500 max-w-md mx-auto leading-relaxed">
          {{ t('dashboard.emptyDesc') }}
        </p>
        <div class="mt-6 flex items-center justify-center gap-3">
          <AppButton @click="startNewProject">+ {{ t('dashboard.emptyCreate') }}</AppButton>
          <AppButton variant="secondary" @click="startNewProject">
            {{ t('dashboard.emptyDocs') }}
          </AppButton>
        </div>
      </div>

      <!-- Populated -->
      <template v-else-if="featured">
        <!-- Featured hero — honest metrics only (no 7-day chart, no inspected count) -->
        <article
          data-testid="dashboard-featured"
          class="rounded-xl bg-white border border-border-default shadow-card p-6 hover:shadow-pop transition cursor-pointer"
          @click="openProject(featured)"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-flex items-center h-6 px-2 rounded-full bg-primary-50 border border-primary-100 text-[11px] font-semibold uppercase tracking-wide text-primary-800"
            >
              {{ t('dashboard.featured') }}
            </span>
            <span
              class="inline-flex items-center gap-1.5 h-6 px-2 rounded-full text-[11px] font-semibold uppercase tracking-wide"
              :class="[statusBadge[featured.status].bg, statusBadge[featured.status].text]"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge[featured.status].dot" />
              {{ t(statusBadge[featured.status].key) }}
            </span>
          </div>

          <h3 class="mt-4 text-2xl font-semibold text-ink-900">{{ featured.name }}</h3>
          <p class="mt-1 text-sm text-ink-500 font-mono">
            {{ featured.slug }} · {{ t('dashboard.updatedAt', { time: relTime(featured.updated_at) }) }}
          </p>

          <div class="mt-6 grid grid-cols-3 gap-6 max-w-md">
            <div>
              <p class="text-2xl font-semibold font-mono tabular-nums text-ink-900">
                {{ featured.bom_count }}
              </p>
              <p class="mt-0.5 text-[11px] font-mono uppercase tracking-wider text-ink-500">
                {{ t('dashboard.bomItems') }}
              </p>
            </div>
            <div>
              <p
                class="text-2xl font-semibold font-mono tabular-nums"
                :class="featured.latest_map != null ? 'text-primary-700' : 'text-ink-400'"
              >
                {{ formatPct(featured.latest_map) }}
              </p>
              <p class="mt-0.5 text-[11px] font-mono uppercase tracking-wider text-ink-500">
                {{ t('dashboard.mapLabel') }}
              </p>
            </div>
            <div>
              <p class="text-2xl font-semibold text-ink-900 capitalize">
                {{ t(statusBadge[featured.status].key) }}
              </p>
              <p class="mt-0.5 text-[11px] font-mono uppercase tracking-wider text-ink-500">
                {{ t('dashboard.statusLabel') }}
              </p>
            </div>
          </div>

          <div class="mt-6 flex justify-end">
            <span class="text-sm font-medium text-primary-700">{{ t('dashboard.open') }} →</span>
          </div>
        </article>

        <!-- Remaining projects -->
        <div
          data-testid="dashboard-projects"
          class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
        >
          <article
            v-for="p in restProjects"
            :key="p.id"
            data-testid="dashboard-project-card"
            class="rounded-xl bg-white border border-border-default shadow-card p-5 hover:shadow-pop transition cursor-pointer flex flex-col"
            @click="openProject(p)"
          >
            <span
              class="inline-flex items-center gap-1.5 h-6 px-2 rounded-full text-[11px] font-semibold uppercase tracking-wide self-start"
              :class="[statusBadge[p.status].bg, statusBadge[p.status].text]"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge[p.status].dot" />
              {{ t(statusBadge[p.status].key) }}
            </span>

            <h3 class="mt-3 text-base font-semibold text-ink-900 truncate">{{ p.name }}</h3>
            <p class="text-xs text-ink-500 font-mono truncate">{{ p.slug }}</p>

            <div class="mt-4 flex items-end gap-6">
              <div>
                <p
                  class="text-lg font-semibold font-mono tabular-nums"
                  :class="p.latest_map != null ? 'text-primary-700' : 'text-ink-400'"
                >
                  {{ formatPct(p.latest_map) }}
                </p>
                <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
                  {{ t('dashboard.mapLabel') }}
                </p>
              </div>
              <div>
                <p class="text-lg font-semibold font-mono tabular-nums text-ink-900">
                  {{ p.bom_count }}
                </p>
                <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
                  {{ t('dashboard.bomShort') }}
                </p>
              </div>
            </div>

            <div class="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between">
              <span class="text-xs text-ink-400 font-mono">{{ relTime(p.updated_at) }}</span>
              <span class="text-xs font-medium text-primary-700">{{ t('dashboard.open') }} →</span>
            </div>
          </article>
        </div>
      </template>
    </section>
  </div>
</template>
