import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  getOpenRouterKey,
  setOpenRouterKey,
  getUserId,
  setUserId,
  getInstanceId,
  setInstanceId,
} from '../../api/client'

describe('api/client localStorage helpers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('getOpenRouterKey returns empty string by default', () => {
    expect(getOpenRouterKey()).toBe('')
  })

  it('setOpenRouterKey persists and getOpenRouterKey retrieves it', () => {
    setOpenRouterKey('sk-or-abc')
    expect(getOpenRouterKey()).toBe('sk-or-abc')
  })

  it('getUserId returns default local-user by default', () => {
    expect(getUserId()).toBe('local-user')
  })

  it('setUserId persists and getUserId retrieves it', () => {
    setUserId('user-123')
    expect(getUserId()).toBe('user-123')
  })

  it('getInstanceId returns empty string by default', () => {
    expect(getInstanceId()).toBe('')
  })

  it('setInstanceId persists and getInstanceId retrieves it', () => {
    setInstanceId('inst-xyz')
    expect(getInstanceId()).toBe('inst-xyz')
  })
})
