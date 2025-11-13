# CLAUDE.md - AI-Assisted Development Guidelines

## How to Use
At the start of each session, tell Claude: "Follow the guidelines in CLAUDE.md"

**Tip for Complex Instructions:** Use XML tags to structure your requests (e.g., `<context>`, `<instructions>`, `<example>`)

## Project Context
**IMPORTANT:** Before beginning work, read `proofsynch-overview.md` to understand:
- Project goals and requirements
- Tech stack and architecture
- Project structure and file organization
- Common commands (dev server, tests, build, lint)
- Established coding patterns
- File boundaries (what's safe to edit vs. what to avoid)

This file (CLAUDE.md) defines HOW to work. The project_overview.md defines WHAT you're building.

## 1. Core Philosophy & Interaction

### 1.1. Code Quality
* **Modularity:** Code should be modular and extensible.
* **Future-Proofing:** Solutions should be "future-proof," anticipating potential (but not yet implemented) features.
* **File Size:** No single file should exceed approximately 1500 lines. If it does, the AI must suggest breaking it into smaller, logical modules.

### 1.2. Decision Making
The AI is an assistant, not the final authority.
* **Present Options:** For any non-trivial implementation (e.g., "should this be a class or a one-off function?", "is an interface appropriate here?"), the AI must present 2-3 options.
* **Pros & Cons:** Each option must be accompanied by a brief list of pros and cons.
* **User Authority:** The user (with domain-level expertise) will make the final decision. This is especially true for choices regarding user-facing customizability vs. a streamlined, simple workflow.

### 1.3. Proactive Clarification
The AI must ask clarifying questions to ensure consistency.
* **Pattern Generalization:** When the user describes a new pattern or logic, the AI must ask: "Is this a general pattern that should be applied to all future functions of this type, or is it a one-off for this specific case?"

### 1.4. Error Handling
* All errors must be caught and logged with sufficient context to debug
* User-facing errors must be clear and actionable (e.g., "File not found: config.json" not "Error code 2")
* Debug mode shows stack traces; production mode does not

### 1.5. Future-Proofing Guidelines
* **Configuration over Hardcoding:** Use config files or constants for values that might change (e.g., file paths, API endpoints, UI text)
* **Design for Extension:** Structure code so new features can be added without modifying existing code (Open/Closed Principle)
* **Avoid Premature Optimization:** Don't add abstraction layers or complex patterns "just in case" - ask first if the added complexity is worth it
* **When in Doubt, Ask:** If a future-proof solution requires significant extra complexity, present it as an option with pros/cons rather than implementing it directly

### 1.6. Pattern Documentation & Reuse
* **Document General Patterns:** When a pattern is established as "general" (not a one-off), it must be documented in `project_overview.md` under a "Coding Patterns" section
* **Check Before Proposing:** Before suggesting a new approach, AI must check existing documented patterns to maintain consistency
* **Pattern Format:** Document as: "Pattern Name: Brief description + where it applies"
  - Example: "Error Handling: All API calls use try/catch with context logging (applies to all external integrations)"
* **Contradiction Check:** Before adding a pattern to `project_overview.md`, AI must verify it doesn't contradict existing patterns or guidelines. If a contradiction is detected:
  1. Warn the user about the specific contradiction
  2. Ask the user to clarify their intent
  3. If clarification resolves the contradiction, proceed with documenting the pattern
  4. If contradiction remains, ask: "Would you like to implement this as a one-time exception, or make it a general pattern anyway (which may override/conflict with existing patterns)?"

### 1.7. Dependency Management
* **Research Libraries:** AI can freely search for reputable libraries to solve problems
* **Safety & Popularity Check:** Before suggesting a library, AI must search for information about its safety, popularity, and maintenance status
* **Ask for Approval:** AI must ask before adding any new library and provide:
  1. **General Purpose:** What the library does overall
  2. **Specific Use:** How it will be used in this project
  3. **Safety/Popularity:** Key findings (download count, last update, known vulnerabilities, community trust)
* **Assumption:** Developer will generally approve any safe, well-maintained library
* **Document & Track:** 
  - New dependencies must be noted in `development_log.md`
  - All Python dependencies must be added to `requirements.txt` with version numbers
  - Ensure `requirements.txt` stays updated when dependencies are added or removed

### 1.8. File Splitting
* **Size Limit:** No file should exceed 1500 lines
* **Logical Boundaries:** Split files along functional or logical boundaries, not arbitrarily
* **Proactive Warning:** AI should suggest splitting when a file reaches 1200 lines

## 2. Mandatory Debug Mode

All projects must include a "debug mode."

* **Toggle:** Debug mode should be controlled via an environment variable (e.g., `DEBUG=true`) or a config file setting.
* **Streamlined Testing:** This mode must use default parameters to streamline development (e.g., automatically opening a default test file instead of prompting for a file).
* **Verbose Logging:** When in debug mode, the application must write verbose logs to the terminal. These logs are **not** written when debug mode is off.
* **Log Content:**
    1.  **Program Flow:** Messages describing the program's execution flow ("Starting Step X...", "Data Y processed...").
    2.  **Performance Timings:** Each programmatic step must be timed. The log must state how long that specific step took to complete.
* **Timing Format:**
    * Timestamps must be included to assess performance.
    * Durations should be printed in a sensible, human-readable unit.
    * **Example Output:**
    ```
    [DEBUG 14:32:01] Starting FileParsing...
    [DEBUG 14:32:01] FileParsing took 842 ms
    [DEBUG 14:32:02] Starting DataAnalysis...
    [DEBUG 14:32:13] DataAnalysis took 11.3 seconds
    ```

## 3. AI-Managed Documentation System

The AI is responsible for maintaining the following set of markdown files.

**Update Timing:**
* `development_log.md`: Update after each significant feature completion or bug fix
* `human_summary.md`: Update at the end of each conversation session
* `scratchpad.md`: Update when discussing potential future features or refinements
* `project_overview.md`: Never update without explicit user permission

### 3.1. `project_overview.md`
* **Purpose:** The primary source of truth. Contains the project's high-level goals, requirements, and architecture.
* **Priority:** **Primary.** All development must align with this file.
* **AI Rules:**
    * The AI *must not* change this file without explicit user permission.
    * The AI *may* suggest changes to resolve ambiguities or discrepancies it identifies.

### 3.2. `development_log.md`
* **Purpose:** A timestamped (date and time) log of all significant changes made to the codebase.
* **AI Rules:**
    * The AI must update this file after every major change.
    * **Feature Summary:** New features must be summarized in 3-4 sentences.
    * **Snag/Bug Summary:** Snags or bugs encountered must be summarized in 1-2 sentences, along with their resolution.
    * **Refinement Check:** After logging a feature, the AI should note if it's incomplete or ask, "Does this feature need further refinement?"

### 3.3. `scratchpad.md`
* **Purpose:** A secondary brainstorming document for future ideas, potential features, and items needing refinement.
* **Priority:** **Secondary.** Ideas here are not yet approved and serve as suggestions.
* **AI Rules:**
    * The AI *can* read this file when relevant
    * **Suggest Only When Asked:** AI should reference scratchpad items when user asks "what's next?" or similar, but should not proactively suggest them
    * **Example Response:** "In the scratchpad, you mentioned wanting to refactor the 'User' class. Would you like to work on that now?"

### 3.4. `human_summary.md`
* **Purpose:** A high-level status report *exclusively for human consumption*.
* **AI Rules:**
    * **CRITICAL: The AI MUST NOT use this file for direction or context.** It is an *output-only* file for the user.
* **Contents (To be updated by AI):**
    1.  **Project Status:** A 3-4 sentence summary of the project's current state (what was done last, what's outstanding).
    2.  **File Directory:** A list of all files in the project, each with a one-sentence description of its purpose.

## 4. Testing
* AI should suggest tests for complex business logic
* Tests should focus on critical functionality, not edge cases

## 5. Quick Reference Checklist

Before finalizing code, AI must verify:
- [ ] File under 1500 lines (suggest splitting if over)
- [ ] Options presented for non-trivial decisions (with pros/cons)
- [ ] Debug logging implemented for new features
- [ ] Debug mode toggle works correctly
- [ ] `development_log.md` updated with feature/bug summary
- [ ] `human_summary.md` updated if end of session
- [ ] No changes to `project_overview.md` without permission
- [ ] Error handling includes context and user-friendly messages
- [ ] Tests suggested for complex business logic (if applicable)
