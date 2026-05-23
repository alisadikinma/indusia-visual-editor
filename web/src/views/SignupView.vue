<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

const email = ref("");
const password = ref("");
const localError = ref<string | null>(null);

async function submit(): Promise<void> {
  localError.value = null;
  try {
    await auth.signup({ email: email.value, password: password.value });
    router.push("/");
  } catch (e: unknown) {
    localError.value =
      e && typeof e === "object" && "response" in e
        ? (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? null
        : null;
    localError.value ??= "Gagal membuat akun.";
  }
}
</script>

<template>
  <main class="signup-shell" data-testid="signup-view">
    <form class="signup-card" @submit.prevent="submit">
      <h1>Daftar Akun Baru</h1>
      <p class="muted">Akun bergabung dengan organisasi default.</p>

      <label>
        Email
        <input
          v-model="email"
          type="email"
          required
          autocomplete="email"
          data-testid="signup-email"
        />
      </label>

      <label>
        Kata sandi (min 8 karakter)
        <input
          v-model="password"
          type="password"
          required
          minlength="8"
          autocomplete="new-password"
          data-testid="signup-password"
        />
      </label>

      <button
        type="submit"
        :disabled="auth.loading"
        data-testid="signup-submit"
      >
        {{ auth.loading ? "Memproses..." : "Buat akun" }}
      </button>

      <p v-if="localError" class="error" data-testid="signup-error">
        {{ localError }}
      </p>

      <p class="footnote">
        Sudah punya akun?
        <router-link to="/login">Masuk di sini</router-link>
      </p>
    </form>
  </main>
</template>

<style scoped>
.signup-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f7f7f8;
  padding: 1.5rem;
}
.signup-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 2rem;
  max-width: 360px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.signup-card h1 {
  margin: 0;
  font-size: 1.25rem;
}
.muted {
  color: #6b7280;
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.875rem;
  color: #374151;
}
input {
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  font-size: 0.875rem;
}
button {
  margin-top: 0.5rem;
  padding: 0.625rem 1rem;
  background: #111827;
  color: white;
  border: 0;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}
button:disabled {
  background: #6b7280;
  cursor: not-allowed;
}
.error {
  color: #b91c1c;
  font-size: 0.875rem;
  margin: 0;
}
.footnote {
  font-size: 0.8rem;
  color: #6b7280;
  margin: 0;
  text-align: center;
}
</style>
