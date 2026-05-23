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
    await auth.login({ email: email.value, password: password.value });
    router.push("/");
  } catch (e: unknown) {
    localError.value =
      e && typeof e === "object" && "response" in e
        ? (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? null
        : null;
    localError.value ??= "Email atau kata sandi salah.";
  }
}
</script>

<template>
  <main class="login-shell" data-testid="login-view">
    <form class="login-card" @submit.prevent="submit">
      <h1>Masuk ke Indusia Visual Editor</h1>
      <p class="muted">Akun MI / operator pabrik.</p>

      <label>
        Email
        <input
          v-model="email"
          type="email"
          required
          autocomplete="email"
          data-testid="login-email"
        />
      </label>

      <label>
        Kata sandi
        <input
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
          data-testid="login-password"
        />
      </label>

      <button
        type="submit"
        :disabled="auth.loading"
        data-testid="login-submit"
      >
        {{ auth.loading ? "Memproses..." : "Masuk" }}
      </button>

      <p v-if="localError" class="error" data-testid="login-error">
        {{ localError }}
      </p>

      <p class="footnote">
        Belum punya akun?
        <router-link to="/signup">Daftar di sini</router-link>
      </p>
    </form>
  </main>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f7f7f8;
  padding: 1.5rem;
}
.login-card {
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
.login-card h1 {
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
