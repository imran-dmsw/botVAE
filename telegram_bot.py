import io
import json
import logging
import os

import pandas as pd
import anthropic
from openai import OpenAI
from pydantic import ValidationError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from engine.models import ScenarioInput
from engine.simulation import simulate
from reports.generator import generate_markdown_report, generate_pdf_report

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _load_local_env() -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    env_path = ".env"
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


HELP_TEXT = (
    "Commandes disponibles:\n"
    "- /start : démarrer le bot\n"
    "- /help : afficher l'aide\n"
    "- /test : mode conversation (questions/réponses)\n"
    "- /wizard : assistant interactif pas-à-pas\n"
    "- /cancel : annuler l'assistant en cours\n"
    "- /template : modèle simple et lisible\n"
    "- /templatefull : JSON complet (avancé)\n"
    "- /simulate <json> : lancer une simulation\n\n"
    "Vous pouvez aussi envoyer directement un JSON dans un message.\n"
    "IA activable via ANTHROPIC_API_KEY (Claude) ou OPENAI_API_KEY dans .env."
)

FAQ_RESPONSES = {
    "bonjour": "Bonjour, je suis prêt. Tu peux me poser des questions sur le bot ou lancer une simulation.",
    "salut": "Salut. Je peux répondre à tes questions de test et exécuter une simulation JSON.",
    "aide": "Utilise /help pour les commandes, /test pour discuter, /template pour obtenir un JSON.",
    "help": "Utilise /help pour les commandes, /test pour discuter, /template pour obtenir un JSON.",
    "que peux tu faire": (
        "Je peux:\n"
        "- répondre à des questions de test sur le bot,\n"
        "- générer un template de scénario,\n"
        "- simuler un scénario JSON et renvoyer un rapport."
    ),
    "comment simuler": "Envoie /template puis /simulate <json>, ou envoie directement un JSON.",
    "merci": "Avec plaisir.",
}

WIZARD_FIELDS = [
    {
        "key": "scenario_name",
        "prompt": "1/8 Nom du scénario ? (ex: Lancement Printemps)",
        "cast": str,
    },
    {
        "key": "period",
        "prompt": "2/8 Période (1 à 15) ?",
        "cast": int,
        "min": 1,
        "max": 15,
    },
    {
        "key": "price",
        "prompt": "3/8 Prix unitaire en CAD ? (ex: 2500)",
        "cast": float,
        "min": 1.0,
    },
    {
        "key": "production",
        "prompt": "4/8 Nombre d'unités produites ? (ex: 1000)",
        "cast": int,
        "min": 0,
    },
    {
        "key": "marketing_budget",
        "prompt": "5/8 Budget marketing en CAD ? (ex: 50000)",
        "cast": float,
        "min": 0.0,
    },
    {
        "key": "rd_budget",
        "prompt": "6/8 Budget R&D en CAD ? (ex: 15000)",
        "cast": float,
        "min": 0.0,
    },
    {
        "key": "segment",
        "prompt": (
            "7/8 Segment cible ?\n"
            "Choix: urbains_presses, prudentes_confort, endurants_performants, "
            "nomades_multimodaux, familles_cargo, aventuriers_tt"
        ),
        "cast": str,
        "choices": {
            "urbains_presses",
            "prudentes_confort",
            "endurants_performants",
            "nomades_multimodaux",
            "familles_cargo",
            "aventuriers_tt",
        },
    },
    {
        "key": "model_range",
        "prompt": "8/8 Gamme ? (entry, mid, premium)",
        "cast": str,
        "choices": {"entry", "mid", "premium"},
    },
]


def _ai_provider() -> str:
    explicit = os.getenv("AI_PROVIDER", "").strip().lower()
    if explicit in {"anthropic", "openai"}:
        return explicit
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return ""


def _ai_enabled() -> bool:
    return bool(_ai_provider())


def _ai_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _ai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def _anthropic_fallback_models() -> list:
    # Ordered from newer/high quality to broadly available fallback models.
    return [
        _anthropic_model(),
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "claude-opus-4-5-20251101",
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
    ]


def _ask_ai(system_prompt: str, user_prompt: str) -> str:
    if not _ai_enabled():
        raise RuntimeError("IA non configurée")
    provider = _ai_provider()
    if provider == "anthropic":
        client = _anthropic_client()
        last_error = None
        tried = []
        for model_name in _anthropic_fallback_models():
            if model_name in tried:
                continue
            tried.append(model_name)
            try:
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=700,
                    temperature=0.3,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                parts = []
                for block in resp.content:
                    text = getattr(block, "text", "")
                    if text:
                        parts.append(text)
                return "\n".join(parts).strip()
            except anthropic.NotFoundError as e:
                last_error = e
                logger.warning("Anthropic model unavailable: %s", model_name)
                continue
        if last_error:
            raise last_error
        raise RuntimeError("Aucun modele Anthropic disponible")
    if provider == "openai":
        client = _ai_client()
        resp = client.chat.completions.create(
            model=_ai_model(),
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    raise RuntimeError("Provider IA non supporté")


def _ai_answer_question(question: str) -> str:
    system_prompt = (
        "Tu es un assistant expert en simulation marketing VAE. "
        "Réponds en français simple, concret, orienté action. "
        "Si la question est vague, propose 3 prochaines actions courtes."
    )
    return _ask_ai(system_prompt, question)


def _ai_improvement_advice(scenario: ScenarioInput, result) -> str:
    system_prompt = (
        "Tu es un consultant stratégie marketing. "
        "À partir d'un scénario et de ses résultats, propose un plan d'amélioration "
        "en 5 points max, avec ajustements chiffrés quand possible. "
        "Format: puces courtes."
    )
    payload = {
        "scenario": scenario.model_dump(),
        "result": result.model_dump(),
    }
    return _ask_ai(system_prompt, json.dumps(payload, ensure_ascii=False))


def _strip_json_fence(text: str) -> str:
    payload = text.strip()
    if payload.startswith("```") and payload.endswith("```"):
        payload = payload[3:-3].strip()
        if payload.lower().startswith("json"):
            payload = payload[4:].strip()
    return payload


def _extract_json_candidate(text: str) -> str:
    content = text.strip()
    if content.startswith("/simulate"):
        content = content[len("/simulate") :].strip()
    return _strip_json_fence(content)


def _looks_like_json_payload(text: str) -> bool:
    stripped = _strip_json_fence(text.strip())
    return stripped.startswith("{") and stripped.endswith("}")


def _answer_general_question(text: str) -> str:
    normalized = " ".join(text.lower().strip().split())
    for key, response in FAQ_RESPONSES.items():
        if key in normalized:
            return response
    return (
        "Question reçue. Pour tester rapidement, essaie:\n"
        "- 'Que peux-tu faire ?'\n"
        "- 'Comment simuler ?'\n"
        "- 'Donne-moi un template'\n\n"
        "Si tu veux une simulation, envoie /template puis /simulate <json>."
    )


def _result_summary(result) -> str:
    status = "Valide" if result.is_valid else "Non valide"
    return (
        f"Résultat: {status}\n"
        f"Scénario: {result.scenario_name}\n"
        f"Ventes: {result.sales:,} unités\n"
        f"CA: {result.revenue:,.0f} $\n"
        f"Profit: {result.profit:,.0f} $\n"
        f"Marge: {result.margin * 100:.1f}%\n"
        f"Part marché: {result.market_share * 100:.2f}%\n"
        f"Innovation: {result.innovation_score:.1f}/10\n"
        f"Durabilité: {result.sustainability_score:.1f}/10"
    )


def _build_xlsx_report_bytes(scenario: ScenarioInput, result) -> bytes:
    scenario_df = pd.DataFrame(
        [{"field": k, "value": v} for k, v in scenario.model_dump().items()]
    )
    result_df = pd.DataFrame(
        [{"metric": k, "value": v} for k, v in result.model_dump().items()]
    )
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        scenario_df.to_excel(writer, index=False, sheet_name="scenario")
        result_df.to_excel(writer, index=False, sheet_name="result")
    return bio.getvalue()


def _wizard_reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard_active", None)
    context.user_data.pop("wizard_step", None)
    context.user_data.pop("wizard_answers", None)


def _wizard_next_prompt(context: ContextTypes.DEFAULT_TYPE) -> str:
    step = context.user_data.get("wizard_step", 0)
    return WIZARD_FIELDS[step]["prompt"]


def _parse_wizard_answer(field_cfg: dict, raw_text: str):
    caster = field_cfg["cast"]
    value = caster(raw_text.strip())
    if "min" in field_cfg and value < field_cfg["min"]:
        raise ValueError(f"Valeur minimale: {field_cfg['min']}")
    if "max" in field_cfg and value > field_cfg["max"]:
        raise ValueError(f"Valeur maximale: {field_cfg['max']}")
    if "choices" in field_cfg and str(value) not in field_cfg["choices"]:
        allowed = ", ".join(sorted(field_cfg["choices"]))
        raise ValueError(f"Choix invalide. Valeurs possibles: {allowed}")
    return value


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /start from user=%s", update.effective_user.id)
    await update.message.reply_text(
        "Bot Marketing VAE connecté sur Telegram.\n\n" + HELP_TEXT
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /help from user=%s", update.effective_user.id)
    await update.message.reply_text(HELP_TEXT)


async def template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /template from user=%s", update.effective_user.id)
    simple_template = {
        "scenario_name": "Scenario Test",
        "period": 1,
        "model_name": "AVE-SwiftRide M1",
        "price": 2500,
        "production": 1000,
        "marketing_budget": 50000,
        "rd_budget": 15000,
        "segment": "urbains_presses",
        "model_range": "mid",
    }
    template_json = json.dumps(simple_template, ensure_ascii=False, indent=2)
    await update.message.reply_text(
        "Modèle simple (copie, modifie, puis envoie avec /simulate):\n\n"
        "1) Change le nom du scénario\n"
        "2) Ajuste prix / production / budgets\n"
        "3) Envoie: /simulate { ... }\n\n"
        f"```json\n{template_json}\n```",
        parse_mode="Markdown",
    )


async def template_full(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /templatefull from user=%s", update.effective_user.id)
    scenario = ScenarioInput()
    template_json = json.dumps(scenario.model_dump(), ensure_ascii=False, indent=2)
    await update.message.reply_text(
        "Template JSON complet (mode avancé):\n\n"
        f"```json\n{template_json}\n```",
        parse_mode="Markdown",
    )


async def test_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /test from user=%s", update.effective_user.id)
    await update.message.reply_text(
        "Mode conversation activé.\n"
        "Pose-moi une question libre (ex: 'Que peux-tu faire ?').\n"
        "Pour une simulation chiffrée, utilise /template puis /simulate."
    )


async def wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /wizard from user=%s", update.effective_user.id)
    context.user_data["wizard_active"] = True
    context.user_data["wizard_step"] = 0
    context.user_data["wizard_answers"] = {}
    await update.message.reply_text(
        "Assistant simulation lancé.\n"
        "Réponds aux questions une par une.\n"
        "Tu peux arrêter avec /cancel.\n\n"
        + _wizard_next_prompt(context)
    )


async def wizard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /cancel from user=%s", update.effective_user.id)
    _wizard_reset(context)
    await update.message.reply_text("Assistant annulé.")


async def _finish_wizard_and_simulate(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    answers = context.user_data.get("wizard_answers", {})
    payload = ScenarioInput().model_dump()
    payload.update(answers)
    payload["marketing_channels"] = {
        "digital": float(payload.get("marketing_budget", 0.0)),
        "social_media": 0.0,
        "influencers": 0.0,
        "display": 0.0,
        "events": 0.0,
    }

    try:
        scenario = ScenarioInput(**payload)
        result = simulate(scenario)
    except ValidationError as e:
        _wizard_reset(context)
        await update.message.reply_text(f"Validation échouée:\n{e}")
        return
    except Exception as e:
        _wizard_reset(context)
        await update.message.reply_text(f"Erreur simulation: {e}")
        return

    _wizard_reset(context)
    await update.message.reply_text("Simulation terminée ✅")
    await update.message.reply_text(_result_summary(result))

    if _ai_enabled():
        try:
            advice = _ai_improvement_advice(scenario, result)
            if advice:
                await update.message.reply_text("🧠 Recommandations IA:\n" + advice)
        except Exception as e:
            logger.exception("AI advice failed")
            await update.message.reply_text(f"IA indisponible pour recommandations: {e}")

    pdf_bytes = generate_pdf_report(scenario, result)
    pdf_doc = io.BytesIO(pdf_bytes)
    pdf_doc.name = f"rapport_{result.scenario_name.replace(' ', '_')}.pdf"
    await update.message.reply_document(document=pdf_doc, caption="Rapport PDF")

    xlsx_bytes = _build_xlsx_report_bytes(scenario, result)
    xlsx_doc = io.BytesIO(xlsx_bytes)
    xlsx_doc.name = f"rapport_{result.scenario_name.replace(' ', '_')}.xlsx"
    await update.message.reply_document(document=xlsx_doc, caption="Rapport Excel")

    report_md = generate_markdown_report(scenario, result)
    md_doc = io.BytesIO(report_md.encode("utf-8"))
    md_doc.name = f"rapport_{result.scenario_name.replace(' ', '_')}.md"
    await update.message.reply_document(document=md_doc, caption="Rapport Markdown")


async def simulate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if update.effective_user:
        logger.info("Received /simulate from user=%s", update.effective_user.id)

    raw_text = update.message.text
    candidate = _extract_json_candidate(raw_text)

    if not candidate:
        await update.message.reply_text(
            "Je n'ai pas trouvé de JSON. Utilisez /template puis /simulate <json>."
        )
        return

    try:
        payload = json.loads(candidate)
        scenario = ScenarioInput(**payload)
        result = simulate(scenario)
    except json.JSONDecodeError as e:
        await update.message.reply_text(f"JSON invalide: {e}")
        return
    except ValidationError as e:
        await update.message.reply_text(f"Validation scénario échouée:\n{e}")
        return
    except Exception as e:
        logger.exception("Simulation failed")
        await update.message.reply_text(f"Erreur simulation: {e}")
        return

    await update.message.reply_text(_result_summary(result))

    if _ai_enabled():
        try:
            advice = _ai_improvement_advice(scenario, result)
            if advice:
                await update.message.reply_text("🧠 Recommandations IA:\n" + advice)
        except Exception as e:
            logger.exception("AI advice failed")
            await update.message.reply_text(f"IA indisponible pour recommandations: {e}")

    report_md = generate_markdown_report(scenario, result)
    report_bytes = io.BytesIO(report_md.encode("utf-8"))
    report_bytes.name = f"rapport_{result.scenario_name.replace(' ', '_')}.md"
    await update.message.reply_document(document=report_bytes, caption="Rapport Markdown")


async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # If message looks like JSON, run simulation. Otherwise answer in conversation mode.
    if update.effective_user:
        logger.info("Received text from user=%s", update.effective_user.id)
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if context.user_data.get("wizard_active"):
        step = context.user_data.get("wizard_step", 0)
        field_cfg = WIZARD_FIELDS[step]
        try:
            value = _parse_wizard_answer(field_cfg, text)
        except Exception as e:
            await update.message.reply_text(
                f"Réponse invalide: {e}\n{field_cfg['prompt']}"
            )
            return

        answers = context.user_data.get("wizard_answers", {})
        answers[field_cfg["key"]] = value
        context.user_data["wizard_answers"] = answers
        context.user_data["wizard_step"] = step + 1

        if context.user_data["wizard_step"] >= len(WIZARD_FIELDS):
            await _finish_wizard_and_simulate(update, context)
            return

        await update.message.reply_text(_wizard_next_prompt(context))
        return

    if _looks_like_json_payload(text):
        await simulate_handler(update, context)
        return

    if _ai_enabled():
        try:
            answer = _ai_answer_question(text)
            if answer:
                await update.message.reply_text(answer)
                return
        except Exception:
            logger.exception("AI Q/A failed, fallback to local responses")

    await update.message.reply_text(_answer_general_question(text))


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Received /ping from user=%s", update.effective_user.id)
    await update.message.reply_text("pong")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info(
            "Received unknown command from user=%s text=%s",
            update.effective_user.id,
            update.message.text if update.message else "",
        )
    await update.message.reply_text(
        "Commande non reconnue. Utilisez /help pour voir les commandes disponibles."
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error", exc_info=context.error)


def main() -> None:
    _load_local_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Définissez TELEGRAM_BOT_TOKEN avant de lancer le bot Telegram.")
    if ":" not in token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN invalide dans .env (format attendu: <id>:<secret>)."
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("test", test_mode))
    app.add_handler(CommandHandler("wizard", wizard_start))
    app.add_handler(CommandHandler("cancel", wizard_cancel))
    app.add_handler(CommandHandler("template", template))
    app.add_handler(CommandHandler("templatefull", template_full))
    app.add_handler(CommandHandler("simulate", simulate_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_error_handler(on_error)

    logger.info("Telegram bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
