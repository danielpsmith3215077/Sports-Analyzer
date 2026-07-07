"""
app.py
Investor-facing Streamlit dashboard for the UFC Fight Prediction Model.
"""

import os
import streamlit as st
import plotly.graph_objects as go
import numpy as np

from env_bootstrap import load_env_local

load_env_local()  # must run before license_gate is imported (reads env at import time)

from database import FightDatabase
from models import PredictionEngine
from license_gate import enforce_license

st.set_page_config(
    page_title="UFC Fight Prediction Engine",
    page_icon="🥊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# License gate (Stage 4) — must pass before any dashboard content renders.
# Re-validates against the SaaS backend on every rerun, so a paused/revoked
# token loses access on the next interaction.
# ---------------------------------------------------------------------------
enforce_license()

# ---------------------------------------------------------------------------
# Cached engine bootstrap
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Building fighter database and training model layers...")
def load_engine():
    db = FightDatabase(n_fighters=500, n_fights=2000, seed=42)
    engine = PredictionEngine(db)
    return db, engine


db, engine = load_engine()

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1a1d29 0%, #22263a 100%);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2d3348;
    }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🥊 UFC Fight Prediction Engine")
st.caption("A six-layer quantitative model: Recursive Elo · Physical Matchup · Contextual Stats · Decay-Adjusted Ensemble · Monte Carlo Simulation")

# ---------------------------------------------------------------------------
# Fighter Selection
# ---------------------------------------------------------------------------
names = db.all_fighter_names()

col1, col_vs, col2 = st.columns([5, 1, 5])
with col1:
    fighter_a = st.selectbox("Corner A", names, index=0)
with col_vs:
    st.markdown("<h2 style='text-align:center; margin-top:32px;'>VS</h2>", unsafe_allow_html=True)
with col2:
    default_b = 1 if names[1] != fighter_a else 2
    fighter_b = st.selectbox("Corner B", names, index=default_b)

run = st.button("Run Prediction", type="primary", width="stretch")

if fighter_a == fighter_b:
    st.warning("Select two different fighters.")
    st.stop()

if run:
    with st.spinner("Running 10,000-iteration Monte Carlo simulation..."):
        result = engine.predict_fight(fighter_a, fighter_b)

    st.session_state["result"] = result

if "result" in st.session_state:
    result = st.session_state["result"]

    if result["fighter_a"] != fighter_a or result["fighter_b"] != fighter_b:
        st.info("Press 'Run Prediction' to update results for the newly selected matchup.")
    else:
        mc = result["monte_carlo"]
        win_pct_a = mc["win_pct"] * 100
        win_pct_b = 100 - win_pct_a

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric(f"{result['fighter_a']} Win Probability", f"{win_pct_a:.1f}%")
        m2.metric(f"{result['fighter_b']} Win Probability", f"{win_pct_b:.1f}%")
        m3.metric("95% Confidence Interval", f"[{mc['ci_low']*100:.1f}%, {mc['ci_high']*100:.1f}%]")

        st.divider()
        st.subheader("Monte Carlo Outcome Distribution (10,000 Simulations)")

        samples = mc["samples"] * 100
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=samples,
            nbinsx=60,
            histnorm="probability density",
            marker=dict(color="rgba(99, 179, 237, 0.55)", line=dict(color="#63b3ed", width=1)),
            name="Simulated Outcomes",
        ))

        mean = samples.mean()
        std = samples.std()
        x_curve = np.linspace(samples.min(), samples.max(), 300)
        gaussian = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_curve - mean) / std) ** 2)
        fig.add_trace(go.Scatter(
            x=x_curve, y=gaussian, mode="lines",
            line=dict(color="#f6ad55", width=3),
            name="Gaussian Fit",
        ))

        fig.add_vline(x=mc["ci_low"] * 100, line_dash="dash", line_color="#a0aec0",
                       annotation_text="2.5%", annotation_position="top")
        fig.add_vline(x=mc["ci_high"] * 100, line_dash="dash", line_color="#a0aec0",
                       annotation_text="97.5%", annotation_position="top")
        fig.add_vline(x=mean, line_color="#68d391", annotation_text="Mean", annotation_position="top")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            xaxis_title=f"{result['fighter_a']} Win Probability (%)",
            yaxis_title="Density",
            height=450,
            showlegend=True,
            margin=dict(t=30, b=30),
        )
        st.plotly_chart(fig, width="stretch")

        st.divider()
        st.subheader("Six-Layer Model Breakdown")

        l1, l2, l3, l4 = st.columns(4)
        with l1:
            st.markdown("**Layer 1 — Recursive Elo**")
            st.write(f"{result['fighter_a']} Elo: `{result['elo_a']:.1f}`")
            st.write(f"{result['fighter_b']} Elo: `{result['elo_b']:.1f}`")
            st.write(f"Elo-implied win prob: `{result['elo_prob']*100:.1f}%`")
        with l2:
            st.markdown("**Opponent Difficulty Score**")
            st.write(f"{result['fighter_a']} ODS: `{result['ods_a']:.3f}`")
            st.write(f"{result['fighter_b']} ODS: `{result['ods_b']:.3f}`")
        with l3:
            st.markdown("**Layer 2 — Physical Matchup**")
            st.write(f"Logistic reg. win prob: `{result['physical_prob']*100:.1f}%`")
        with l4:
            st.markdown("**Layer 3 — Contextual Stats**")
            st.write(f"Contextual win prob: `{result['contextual_prob']*100:.1f}%`")
            st.write(f"Composite A: `{result['contextual_composite_a']:.3f}`")
            st.write(f"Composite B: `{result['contextual_composite_b']:.3f}`")

        l5, l6 = st.columns(2)
        with l5:
            st.markdown("**Layer 5 — Wear & Tear Decay**")
            st.write(f"{result['fighter_a']} performance scalar: `{result['decay_penalty_a']:.3f}`")
            st.write(f"{result['fighter_b']} performance scalar: `{result['decay_penalty_b']:.3f}`")
        with l6:
            st.markdown("**Layer 4 — Weighted Ensemble**")
            st.write(f"Final ensemble win prob ({result['fighter_a']}): `{result['ensemble_prob']*100:.1f}%`")
            st.write("Weights: 40% Elo · 35% Contextual · 25% Physical")

        # -------------------------------------------------------------
        # Stage 3.4 — AI tactical breakdown (Claude or NVIDIA NIM)
        # -------------------------------------------------------------
        st.divider()
        st.subheader("Executive Tactical Breakdown (AI)")

        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
        available_providers = []
        if anthropic_key:
            available_providers.append("Claude (Anthropic)")
        if nvidia_key:
            available_providers.append("NVIDIA NIM")

        if not available_providers:
            st.info(
                "Set ANTHROPIC_API_KEY and/or NVIDIA_API_KEY as environment variables "
                "before launching Streamlit to enable the AI-generated tactical breakdown. "
                "Both providers work — pick whichever key you have."
            )
        else:
            provider = st.radio(
                "AI Provider", available_providers, horizontal=True
            ) if len(available_providers) > 1 else available_providers[0]

            def call_claude(prompt):
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(block.text for block in msg.content if block.type == "text")

            def call_nvidia(prompt, model="meta/llama-3.1-70b-instruct"):
                from openai import OpenAI
                client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=nvidia_key,
                )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    temperature=0.6,
                )
                return resp.choices[0].message.content

            @st.cache_data(show_spinner="Generating tactical breakdown...")
            def get_breakdown(payload_key, prompt, provider_name):
                if provider_name == "Claude (Anthropic)":
                    return call_claude(prompt)
                return call_nvidia(prompt)

            prompt = f"""You are a professional MMA analyst producing an executive tactical
breakdown for investors reviewing a quantitative fight prediction model.

Matchup: {result['fighter_a']} vs {result['fighter_b']}

Layer 1 (Recursive Elo): {result['fighter_a']} Elo {result['elo_a']:.1f}, {result['fighter_b']} Elo {result['elo_b']:.1f}, Elo win probability {result['elo_prob']*100:.1f}%
Opponent Difficulty Scores: {result['fighter_a']} {result['ods_a']:.3f}, {result['fighter_b']} {result['ods_b']:.3f}
Layer 2 (Physical Matchup logistic regression win probability): {result['physical_prob']*100:.1f}%
Layer 3 (Contextual Stats win probability): {result['contextual_prob']*100:.1f}%, composite scores {result['contextual_composite_a']:.3f} vs {result['contextual_composite_b']:.3f}
Layer 4 (Weighted Ensemble win probability for {result['fighter_a']}): {result['ensemble_prob']*100:.1f}%
Layer 5 (Wear-and-tear decay scalars): {result['fighter_a']} {result['decay_penalty_a']:.3f}, {result['fighter_b']} {result['decay_penalty_b']:.3f}
Layer 6 (Monte Carlo, 10000 iterations): {result['fighter_a']} win rate {mc['win_pct']*100:.1f}%, 95% CI [{mc['ci_low']*100:.1f}%, {mc['ci_high']*100:.1f}%]

Write exactly 3 paragraphs. Paragraph 1: summarize the mathematical prediction and which
layers agree or disagree. Paragraph 2: explain the tactical/statistical reasoning behind
the numbers (Elo strength of schedule, physical discrepancies, contextual form, any decay
penalties). Paragraph 3: state the confidence level and key risk factors to the prediction.
Do not use markdown headers, just plain prose paragraphs."""

            try:
                breakdown = get_breakdown(f"{fighter_a}-{fighter_b}-{provider}", prompt, provider)
                st.write(breakdown)
            except Exception as e:
                st.error(f"{provider} API call failed: {e}")

else:
    st.info("Select two fighters and press 'Run Prediction' to generate the model output.")
