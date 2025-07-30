import { useSessionStore } from "../store/sessionStore"
import { inject, provide } from "vue"

const SESSION_STORE_KEY = Symbol('session-store')

export function provideSessionStore() {
  const store = useSessionStore()
  provide(SESSION_STORE_KEY, store)
  return store
}

export function useInjectSessionStore() {
  const store = inject(SESSION_STORE_KEY)
  if (!store) {
    throw new Error('Session store not provided')
  }
  return store
}