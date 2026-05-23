<script setup lang="ts">
/**
 * Per-component F1 bar chart (M9 eval surface).
 *
 * Plain SVG — Chart.js would add ~70KB for one chart. Each bar is rendered
 * inline with a designator label, the F1 score, and an optional prev-run
 * F1 (rendered as a faint outline) for at-a-glance delta visibility.
 */
import { computed } from "vue";

const props = defineProps<{
  f1: Record<string, number>;
  prevF1?: Record<string, number> | null;
}>();

type Row = {
  designator: string;
  f1: number;
  prev: number | null;
};

const rows = computed<Row[]>(() => {
  return Object.entries(props.f1)
    .map(([designator, f1]) => ({
      designator,
      f1,
      prev:
        props.prevF1 && designator in props.prevF1
          ? (props.prevF1[designator] as number)
          : null,
    }))
    .sort((a, b) => a.f1 - b.f1);
});

function widthPct(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function barClass(f1: number): string {
  if (f1 >= 0.85) return "bg-success";
  if (f1 >= 0.7) return "bg-primary";
  if (f1 >= 0.5) return "bg-warning";
  return "bg-danger";
}
</script>

<template>
  <div data-testid="metric-chart" class="space-y-2">
    <div
      v-for="row in rows"
      :key="row.designator"
      class="grid grid-cols-[5rem_1fr_3rem] items-center gap-3"
    >
      <span class="font-mono text-xs text-text-secondary">{{
        row.designator
      }}</span>
      <div class="relative h-3 overflow-hidden rounded-full bg-bg-deep">
        <div
          v-if="row.prev !== null"
          class="absolute inset-y-0 left-0 border-r border-text-tertiary/60"
          :style="{ width: widthPct(row.prev) + '%' }"
          aria-label="F1 sebelumnya"
        ></div>
        <div
          class="absolute inset-y-0 left-0 rounded-full"
          :class="barClass(row.f1)"
          :style="{ width: widthPct(row.f1) + '%' }"
        ></div>
      </div>
      <span class="text-right font-mono text-xs text-text-primary">{{
        row.f1.toFixed(2)
      }}</span>
    </div>
  </div>
</template>
