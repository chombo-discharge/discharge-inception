# Static Analysis Bug Report

## Bug 1 — HDF5 write failure: crash folder doesn't exist (HIGH — most likely cause)

**Files:** `master.inputs`, `CD_ItoKMCBackgroundEvaluatorImplem.H` (`computeDt()`)

When `m_relFieldChange > m_relFieldExitCrit` (currently 0.25), `computeDt()` returns 0.0,
signalling Driver to write plot files to `./crash/`. If that subdirectory doesn't exist,
HDF5 file creation fails.

With `plasma.voltage = 40E3` (up from 29 kV), even a small electron cluster near the rod
tip is likely to exceed the 25% relative threshold in high-field cells.

**Diagnostic:** set `ItoKMCBackgroundEvaluator.rel_field_exit_crit = -1` in master.inputs
to disable the criterion. If the HDF5 failure disappears, this is the cause.

---

## Bug 2 — `m_relFieldExitCrit` uninitialized before `pp.query` (MEDIUM)

**File:** `CD_ItoKMCBackgroundEvaluatorImplem.H`, constructor (~line 29)

`m_maxFieldExitCrit` is explicitly initialized but `m_relFieldExitCrit` is not. `pp.query`
only writes the value if the key is present; if absent, the member is uninitialized UB.
Currently harmless because master.inputs provides the key, but fragile.

```cpp
m_maxFieldExitCrit = std::numeric_limits<Real>::max();  // OK
// m_relFieldExitCrit NOT initialized                   // BUG
pp.query("rel_field_exit_crit", m_relFieldExitCrit);
```

**Fix:** add `m_relFieldExitCrit = std::numeric_limits<Real>::max();` (or -1.0) before the query.

---

## Bug 3 — Race conditions in OpenMP parallel loops (HIGH — can spuriously trigger Bug 1)

**File:** `CD_ItoKMCBackgroundEvaluatorImplem.H`

Three functions accumulate shared variables inside `#pragma omp parallel for` without
atomics or reductions:

| Function | Racy variable(s) |
|---|---|
| `evaluateSpaceChargeEffects()` | `relChange = std::max(relChange, ...)` |
| `integrateElectrodeSurfaceCharge()` | `Enorm +=` |
| `integrateOpticalExcitations()` | `sumPhi +=`, `sumSrc +=` |

The race in `evaluateSpaceChargeEffects` is the most dangerous: a corrupted `relChange`
can spuriously exceed `m_relFieldExitCrit`, triggering the crash-folder write (Bug 1)
even when the physics is fine.

**Fix:** use OpenMP reduction clauses, e.g.:
```cpp
#pragma omp parallel for schedule(runtime) reduction(max:relChange)
```
and similarly `reduction(+:Enorm)`, `reduction(+:sumPhi,sumSrc)`.

---

## Bug 4 — Invalid `static_cast` of `RefCountedPtr` (LOW — dead code, but UB)

**File:** `CD_ItoKMCBackgroundEvaluatorImplem.H`, `integrateOpticalExcitations()` (~line 403)

```cpp
const RefCountedPtr<ItoKMCJSON>& physics =
    static_cast<const RefCountedPtr<ItoKMCJSON>&>(this->m_physics);
```

`RefCountedPtr<Base>` and `RefCountedPtr<Derived>` are unrelated wrapper types;
`static_cast` between their references is undefined behaviour. The variable is never
used (all work goes through `CdrIterator`), so it doesn't crash in practice.

**Fix:** remove the line entirely.

---

## Bug 5 — `secondTownsend` uninitialized; averaging counter never incremented (MEDIUM — inception mode)

**File:** `main.cpp`, lines ~36 and ~60–73

`secondTownsend` is declared but not initialized. The accumulation `secondTownsend +=`
on the first iteration is undefined behaviour. Additionally, `numEmissionMechanisms` is
declared as `0` and never incremented inside the loop, so the averaging ternary always
takes the else branch and forces `secondTownsend = 0.0` regardless of chemistry.json.

```cpp
Real secondTownsend;                   // uninitialized — UB below
...
int numEmissionMechanisms = 0;         // never incremented
for (...) {
    if (products[i] == "e") {
        secondTownsend += ...;         // UB: reads uninitialized value
        // numEmissionMechanisms++;    // missing
    }
}
secondTownsend = (0 > 0) ? .../0 : 0.0;  // always 0.0
```

**Fix:** initialize `secondTownsend = 0.0` and add `numEmissionMechanisms++` inside the
`if` block (or drop the counter entirely and just accumulate the sum, since both electrode
emission reactions use the same efficiency of 1E-3).

---

## Bug 6 — Case mismatch: `App.mode` (Runs.py) vs `app.mode` (main.cpp) (HIGH — study runs)

**Files:** `Studies/PressureStudy/Runs.py`, `main.cpp`

Runs.py writes `App.mode` (capital A) to master.inputs, but main.cpp reads it as:

```cpp
ParmParse app("app");   // lowercase prefix
app.get("mode", mode);
```

Chombo's ParmParse is case-sensitive on the prefix. The configurator would write a new
`App.mode = plasma` line while the original `app.mode = inception` line remains.
`ParmParse("app")` then finds `inception` and ignores the configurator's value — every
study run executes in inception mode regardless of intent.

**Fix:** change the uri in Runs.py from `"App.mode"` to `"app.mode"` in both
`inception_stepper` and `plasma_study_1`.
