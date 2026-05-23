<script setup lang="ts">
/**
 * Worst false-positive / false-negative grid (M9 eval surface).
 *
 * Pulls up to 10 of each from the predictions list. FP = model said "fail"
 * but ground truth was "pass" (false alarm). FN = model said "pass" but
 * ground truth was "fail" (missed defect). FN is the operationally
 * dangerous bucket — a missed defect makes it to the customer.
 */
import { computed } from "vue";

import type { EvalPrediction } from "../api/eval";

const props = defineProps<{
  predictions: EvalPrediction[];
}>();

const MAX_PER_BUCKET = 10;

const falsePositives = computed<EvalPrediction[]>(() => {
  return props.predictions
    .filter((p) => p.is_false_positive)
    .slice()
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_PER_BUCKET);
});

const falseNegatives = computed<EvalPrediction[]>(() => {
  return props.predictions
    .filter((p) => p.is_false_negative)
    .slice()
    .sort((a, b) => a.score - b.score)
    .slice(0, MAX_PER_BUCKET);
});

const hasNothing = computed(
  () => falsePositives.value.length === 0 && falseNegatives.value.length === 0,
);
</script>

<template>
  <div data-testid="prediction-grid" class="space-y-6">
    <p
      v-if="hasNothing"
      class="rounded bg-bg-elevated px-4 py-3 text-sm text-text-secondary"
      data-testid="prediction-empty"
    >
      Tidak ada false-positive atau false-negative pada eval set ini.
    </p>

    <section v-if="falsePositives.length > 0">
      <h3 class="mb-2 font-sans text-sm font-semibold text-text-primary">
        False Positive Terburuk
        <span class="ml-1 text-xs font-normal text-text-tertiary">
          (model bilang fail, sebenarnya pass)
        </span>
      </h3>
      <ul
        class="grid grid-cols-2 gap-3 md:grid-cols-5"
        data-testid="prediction-fp-list"
      >
        <li
          v-for="p in falsePositives"
          :key="`fp-${p.designator}-${p.score}`"
          class="rounded-md border border-danger/40 bg-bg-elevated p-3"
        >
          <p class="font-mono text-xs font-bold text-danger">
            {{ p.designator }}
          </p>
          <p class="mt-1 text-xs text-text-secondary">
            score {{ p.score.toFixed(2) }}
          </p>
        </li>
      </ul>
    </section>

    <section v-if="falseNegatives.length > 0">
      <h3 class="mb-2 font-sans text-sm font-semibold text-text-primary">
        False Negative Terburuk
        <span class="ml-1 text-xs font-normal text-text-tertiary">
          (model bilang pass, sebenarnya fail — bahaya!)
        </span>
      </h3>
      <ul
        class="grid grid-cols-2 gap-3 md:grid-cols-5"
        data-testid="prediction-fn-list"
      >
        <li
          v-for="p in falseNegatives"
          :key="`fn-${p.designator}-${p.score}`"
          class="rounded-md border border-warning/40 bg-bg-elevated p-3"
        >
          <p class="font-mono text-xs font-bold text-warning">
            {{ p.designator }}
          </p>
          <p class="mt-1 text-xs text-text-secondary">
            score {{ p.score.toFixed(2) }}
          </p>
        </li>
      </ul>
    </section>
  </div>
</template>
