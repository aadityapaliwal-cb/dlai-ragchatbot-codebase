# Code Quality Tools Implementation

## Overview
This document describes the code quality tools that have been added to the RAG chatbot development workflow. These tools ensure consistent code formatting, style compliance, and type safety across the Python codebase.

## Changes Made

### 1. Dependencies Added
The following code quality tools were added to `pyproject.toml`:
- **Black** (>=24.0.0): Automatic Python code formatter
- **isort** (>=5.13.0): Import statement sorter
- **flake8** (>=7.0.0): Style guide enforcement (PEP 8)
- **mypy** (>=1.8.0): Static type checker

### 2. Configuration Files

#### pyproject.toml
Added tool configurations:

**Black Configuration:**
- Line length: 88 characters
- Target version: Python 3.13
- Excludes: .venv, build, dist, chroma_db, and other standard directories

**isort Configuration:**
- Profile: black (ensures compatibility with Black)
- Line length: 88 characters
- Skips gitignore files
- Recognizes "backend" as first-party package

**mypy Configuration:**
- Target version: Python 3.13
- Warnings for return types and unused configs
- Ignores missing imports (for third-party libraries without type stubs)

#### .flake8
Created `.flake8` configuration file with:
- Max line length: 88 characters
- Extended ignores: E203, W503, E501, E402, F401, F841
- Excludes standard directories (.venv, build, dist, etc.)
- Max complexity: 25
- Per-file ignores for `__init__.py` files

### 3. Development Scripts

#### format.sh
Automatic code formatting script that:
1. Formats all Python code with Black
2. Sorts all imports with isort

**Usage:**
```bash
./format.sh
```

#### quality-check.sh
Comprehensive quality check script that:
1. Checks code formatting with Black (without modifying files)
2. Verifies import sorting with isort (without modifying files)
3. Runs flake8 linting for style compliance
4. Runs mypy type checking (informational, non-blocking)

**Usage:**
```bash
./quality-check.sh
```

**Exit codes:**
- 0: All critical checks passed
- 1: One or more critical checks failed (Black, isort, or flake8)

### 4. Code Formatting Applied
All Python files in the codebase have been formatted:
- **16 files reformatted** with Black
- **16 files updated** with isort for proper import ordering
- Fixed duplicate import statements in `backend/app.py`

### 5. Files Modified
1. `pyproject.toml` - Added dependencies and tool configurations
2. `.flake8` - Created flake8 configuration
3. `format.sh` - Created formatting script (executable)
4. `quality-check.sh` - Created quality check script (executable)
5. All Python files in `backend/` - Formatted with Black and isort
6. All Python test files in `backend/tests/` - Formatted with Black and isort

## How to Use

### Before Committing Code
Run the quality check to ensure your code meets standards:
```bash
./quality-check.sh
```

If checks fail, run the formatter to auto-fix issues:
```bash
./format.sh
```

### During Development
You can run individual tools:
```bash
# Format code with Black
uv run black .

# Sort imports
uv run isort .

# Check style with flake8
uv run flake8 .

# Type check with mypy
uv run mypy backend/
```

### CI/CD Integration
The `quality-check.sh` script can be integrated into CI/CD pipelines to enforce code quality standards before merging.

## Benefits

1. **Consistency**: All code follows the same formatting standards
2. **Readability**: Properly formatted and organized code is easier to read
3. **Maintainability**: Consistent style reduces cognitive load when switching between files
4. **Error Prevention**: flake8 catches common style issues and potential bugs
5. **Type Safety**: mypy helps identify type-related issues early
6. **Automation**: Formatting scripts reduce manual effort and enforce standards

## Tool Details

### Black
- **Purpose**: Automatic code formatting
- **Philosophy**: "Any color you like, as long as it's black" - eliminates debates about formatting
- **Line Length**: 88 characters (Black's default)

### isort
- **Purpose**: Import statement organization
- **Profile**: Configured to match Black's formatting
- **Sections**: Automatically organizes imports into stdlib, third-party, and first-party sections

### flake8
- **Purpose**: Style guide enforcement (PEP 8 compliance)
- **Configured to ignore**:
  - E203: Whitespace before ':' (conflicts with Black)
  - W503: Line break before binary operator (outdated PEP 8 guidance)
  - E501: Line too long (handled by Black)
  - E402: Module level import not at top of file (needed for some initialization patterns)
  - F401: Module imported but unused (common in test fixtures)
  - F841: Local variable assigned but never used (common in exception handling)

### mypy
- **Purpose**: Static type checking
- **Configuration**: Lenient settings suitable for gradual typing adoption
- **Status**: Non-blocking (informational warnings only)

## Next Steps

### Optional Enhancements
1. **Pre-commit Hooks**: Set up git pre-commit hooks to run quality checks automatically
2. **CI/CD Integration**: Add quality checks to GitHub Actions or other CI systems
3. **Type Annotations**: Gradually add type hints to improve mypy coverage
4. **IDE Integration**: Configure VS Code, PyCharm, or other IDEs to run Black on save

### Recommended Workflow
1. Write code
2. Run `./format.sh` to auto-format
3. Run `./quality-check.sh` to verify quality
4. Commit changes
5. Create pull request

## Troubleshooting

### Quality Check Fails
If `./quality-check.sh` fails:
1. Run `./format.sh` to auto-fix formatting issues
2. Review flake8 errors and fix manually if needed
3. mypy warnings are informational and don't block commits

### Installation Issues
If tools are not available:
```bash
uv sync  # Reinstall all dependencies
```

### Line Ending Issues
If scripts fail with "bad interpreter" error:
```bash
sed -i '' 's/\r$//' format.sh quality-check.sh
chmod +x format.sh quality-check.sh
```

## Summary
Code quality tools have been successfully integrated into the development workflow. The codebase now has consistent formatting, organized imports, and automated quality checks. Developers can use `./format.sh` to format code and `./quality-check.sh` to verify quality before committing changes.

---

# Frontend Changes: Dark/Light Theme Toggle

## Overview
Added a theme toggle feature that allows users to switch between dark and light themes with smooth transitions and persistent preferences.

## Files Modified

### 1. `frontend/index.html`
**Changes:**
- Added theme toggle button positioned in the top-right corner of the page
- Button includes accessible SVG icons (sun for light mode, moon for dark mode)
- Updated CSS and JS version numbers to v10 for cache busting
- Added `aria-label` for accessibility

**Implementation Details:**
```html
<button id="themeToggle" class="theme-toggle" aria-label="Toggle theme">
  <!-- Sun and Moon SVG icons -->
</button>
```

### 2. `frontend/style.css`
**Changes:**

#### Light Theme Variables
- Added comprehensive light theme color palette using `[data-theme="light"]` selector
- Light theme colors include:
  - Background: `#f8fafc` (soft white)
  - Surface: `#ffffff` (pure white)
  - Text Primary: `#0f172a` (dark slate)
  - Text Secondary: `#64748b` (medium gray)
  - Border: `#e2e8f0` (light gray)
  - Assistant Message: `#f1f5f9` (light blue-gray)
  - All other colors maintain good contrast ratios for accessibility

#### Smooth Transitions
- Added global transition rules for theme switching
- Transitions affect: `background-color`, `color`, `border-color`, `box-shadow`
- Duration: 0.3s with ease timing function

#### Theme Toggle Button Styles
- Fixed positioning in top-right corner (1.5rem from top and right)
- Circular button (48px × 48px) with rounded edges
- Hover effects: scale transformation, color change, enhanced shadow
- Focus states for keyboard accessibility
- Active state with scale-down animation
- Icon rotation animation (360° rotation with scale effect)
- Responsive adjustments for mobile (44px × 44px)
- Z-index: 1000 to ensure visibility above other elements

#### Icon Visibility Logic
- Sun icon visible in light theme
- Moon icon visible in dark theme
- Smooth opacity and rotation transitions between icons

### 3. `frontend/script.js`
**Changes:**

#### New Functions Added

**`initializeTheme()`**
- Called on page load to set initial theme
- Checks localStorage for saved user preference
- Falls back to system preference (`prefers-color-scheme`)
- Default theme: respects OS settings

**`toggleTheme()`**
- Toggles between 'light' and 'dark' themes
- Saves preference to localStorage for persistence
- Triggers button animation on click
- Updates `data-theme` attribute on body element

#### Event Listeners
- Click listener on theme toggle button
- Keyboard support for Enter and Space keys
- System theme change listener (only applies if no manual preference set)

#### Global State
- Added `themeToggle` to DOM elements
- Theme preference stored in localStorage as 'theme' key

## Features Implemented

### 1. Theme Toggle Button
- Icon-based design with sun/moon icons
- Smooth rotation animation on toggle
- Positioned in top-right corner
- Fully accessible and keyboard-navigable (Enter/Space keys)
- Hover and focus states for better UX

### 2. Light Theme
- Complete color palette optimized for readability
- High contrast text on light backgrounds
- Adjusted shadows for light mode (softer, less prominent)
- Maintains visual hierarchy from dark theme
- All UI elements work seamlessly in both themes

### 3. Smooth Transitions
- 0.3s ease transitions for all color changes
- Icon rotation animation (0.5s)
- Button hover/active state animations
- No jarring visual changes

### 4. Persistence & Smart Defaults
- Theme preference saved to localStorage
- Persists across browser sessions
- Respects system color scheme preference on first visit
- Auto-updates only when user hasn't set a preference

## User Experience

### How It Works
1. **First Visit:** Theme defaults to user's system preference (dark/light mode)
2. **Manual Toggle:** Click the button in top-right to switch themes
3. **Persistence:** Choice is remembered for future visits
4. **Keyboard Navigation:** Tab to button, press Enter or Space to toggle
5. **System Changes:** If no manual preference, theme auto-updates with OS settings

### Visual Feedback
- Button scales up on hover (1.05×)
- Button scales down on click (0.95×)
- Icon rotates 360° with scale animation
- Border changes to primary color on hover
- Smooth color transitions throughout UI

## Accessibility Features
- Proper `aria-label` on toggle button
- Keyboard navigation support (Tab, Enter, Space)
- High contrast ratios in both themes (WCAG AA compliant)
- Focus rings for keyboard users
- No reliance on color alone for information

## Technical Implementation

### CSS Custom Properties
Both themes use the same variable names, making the switch seamless:
- `--background`, `--surface`, `--surface-hover`
- `--text-primary`, `--text-secondary`
- `--border-color`, `--primary-color`, `--primary-hover`
- `--user-message`, `--assistant-message`
- `--shadow`, `--focus-ring`

### Data Attribute Approach
- Theme applied via `data-theme` attribute on `<body>`
- Values: `"light"` or `"dark"`
- CSS selectors: `[data-theme="light"]` for theme-specific styles
- JavaScript toggles attribute and saves to localStorage

### Browser Compatibility
- Uses modern CSS custom properties (supported in all modern browsers)
- localStorage API (universal support)
- SVG icons (full browser support)
- matchMedia API for system preference detection

## Testing Checklist
- [x] Theme toggle button appears in top-right corner
- [x] Clicking button switches between light and dark themes
- [x] Theme preference persists after page reload
- [x] Keyboard navigation works (Tab + Enter/Space)
- [x] All UI elements readable in both themes
- [x] Smooth transitions between themes
- [x] Icon changes correctly (sun in light, moon in dark)
- [x] Hover and focus states work properly
- [x] Responsive design (works on mobile and desktop)
- [x] Respects system color scheme on first visit

## Browser Storage
- **Key:** `theme`
- **Values:** `"light"` | `"dark"`
- **Location:** localStorage
- **Persistence:** Permanent (until cleared by user)

## Notes
- No external dependencies added
- Pure CSS/JS implementation
- Minimal performance impact
- Maintains existing design language
- All transitions are hardware-accelerated where possible
