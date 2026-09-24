$scenarios = @(
    "T2-Tier1", "T3-Tier1",
    "T1-Tier2", "T2-Tier2", "T3-Tier2", "T4-Tier2",
    "T2-Tier3", "T3-Tier3", "T4-Tier3", "T5-Tier3",
    "T5-Tier4", "T6-Tier4",
    "TBD-Tier5"
)
$models = @("llama-3.3-70b-groq", "gpt-oss-20b")

foreach ($model in $models) {
    foreach ($scenario in $scenarios) {
        Write-Host "=== Running $scenario / $model ===" -ForegroundColor Cyan
        python run_benchmark.py --scenario $scenario --model $model --n 15 --resume
    }
}