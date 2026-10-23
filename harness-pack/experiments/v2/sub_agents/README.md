# C5 Subagents — MAXIMUM POWER CONFIGURATION v2.0

## Available Subagents

### code-reviewer
- Purpose: Review code for quality, security, and performance issues
- When to use: After writing any non-trivial code block
- Input: Code to review + context about what it should do
- Output: List of issues with severity and suggested fixes

### test-writer
- Purpose: Write comprehensive unit tests
- When to use: After implementing any function or class
- Input: Function signatures + expected behavior
- Output: Test files with AAA pattern

### refactorer
- Purpose: Improve code structure without changing behavior
- When to use: When code is duplicated, overly complex, or hard to read
- Input: Code to refactor + target structure
- Output: Refactored code with same behavior

### security-auditor
- Purpose: Check for security vulnerabilities
- When to use: Before any code touches external input or systems
- Input: Code that handles user data, auth, or network
- Output: Security findings with remediation steps

## Subagent Invocation Pattern
1. Define the subagent's task clearly
2. Provide all necessary context
3. Execute the subagent
4. Review and integrate results
5. Discard if results are not useful

## When NOT to Use Subagents
- Simple tasks that can be done directly
- Tasks requiring deep context you already have
- When speed is more important than thoroughness

---
Harness² Studio — Maximum Power Subagents v2.0