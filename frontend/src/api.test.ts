import { describe, expect, it } from 'vitest'
import { describeError, formatBytes } from './api'

describe('describeError', () => {
  it('passes plain messages through', () => {
    expect(describeError('Invalid email or password')).toBe('Invalid email or password')
  })

  it('flattens FastAPI validation errors', () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 10 characters' },
      { loc: ['body', 'full_name'], msg: 'Value error, full_name must not be blank' },
    ]
    expect(describeError(detail)).toBe(
      'password: String should have at least 10 characters; full_name: full_name must not be blank',
    )
  })

  it('falls back when the body is unexpected', () => {
    expect(describeError(undefined, 'Bad Gateway')).toBe('Bad Gateway')
  })
})

describe('formatBytes', () => {
  it.each([
    [null, '—'],
    [512, '512 B'],
    [1536, '1.5 KB'],
    [250 * 1024 * 1024, '250.0 MB'],
    [3 * 1024 ** 3, '3.0 GB'],
  ])('formats %s as %s', (input, expected) => {
    expect(formatBytes(input)).toBe(expected)
  })
})
