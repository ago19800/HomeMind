"""
agent/energy_analyzer.py — Analisi anomalie energetiche con AI.

Funzionamento:
  • Ogni sera alle 23:30 legge i valori energetici del giorno e li salva in storico JSON
  • Ogni mattina alle 07:15 (dopo il briefing) analizza ieri vs media storica
  • Se trova anomalie (consumo +30% / produzione -40% rispetto alla media) chiama l'AI
  • Invia notifica Telegram con spiegazione leggibile

Anomalie rilevate:
  - Consumo casa molto alto / molto basso rispetto alla media
  - Produzione FV molto bassa (giornata nuvolosa? pannelli sporchi?)
  - Autosufficienza crollata (ratio FV/consumo)
  - Prelievo da rete anomalo

Storico: /data/homemind_energy_history.json
  {
    "2026-03-01": {"consumo_casa": 8.2, "produzione_fv": 12.4, "rete_enel": 1.1, "batteria_wh": 3.2},
    "2026-03-02": {...},
    ...
  }
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, date
from utils.timezone_helper import now_local
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.energy_analyzer")

HISTORY_PATH  = Path("/data/homemind_energy_history.json")
HISTORY_DAYS  = 30        # quanti giorni teniamo in storico
SNAPSHOT_HOUR = 23        # ora salvataggio snapshot giornaliero
SNAPSHOT_MIN  = 30
ANALYSIS_HOUR = 7         # ora analisi mattutina
ANALYSIS_MIN  = 15

# Soglie anomalia
THRESHOLD_HIGH = 1.30     # +30% → anomalia alta
THRESHOLD_LOW  = 0.70     # -30% → anomalia bassa
THRESHOLD_FV_LOW = 0.60   # produzione FV: -40% già è anomalia
MIN_HISTORY_DAYS = 5      # minimo giorni in storico per fare analisi


class EnergyAnalyzer:
    def __init__(self, ai, history_client, notifier=None, state_cache_cb=None):
        self.ai             = ai
        self.history_client = history_client
        self.notifier       = notifier
        self._cache_cb      = state_cache_cb
        self._history: dict = {}   # date_str → {cat: value}

    @property
    def _state_cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio scheduler

    async def start(self):
        await self._load_history()
        asyncio.create_task(self._scheduler_snapshot(), name="energy_snapshot")
        asyncio.create_task(self._scheduler_analysis(), name="energy_analysis")
        logger.info(
            "EnergyAnalyzer avviato — snapshot %02d:%02d, analisi %02d:%02d",
            SNAPSHOT_HOUR, SNAPSHOT_MIN, ANALYSIS_HOUR, ANALYSIS_MIN
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Schedulers

    async def _scheduler_snapshot(self):
        """Ogni sera alle 23:30 salva i valori del giorno nello storico."""
        while True:
            await self._wait_until(SNAPSHOT_HOUR, SNAPSHOT_MIN)
            try:
                await self._take_snapshot()
            except Exception as e:
                logger.error("EnergyAnalyzer snapshot error: %s", e)

    async def _scheduler_analysis(self):
        """Ogni mattina alle 07:15 analizza ieri vs media."""
        # Piccolo delay iniziale per non partire subito al boot
        await asyncio.sleep(30)
        while True:
            await self._wait_until(ANALYSIS_HOUR, ANALYSIS_MIN)
            try:
                await self._run_analysis()
            except Exception as e:
                logger.error("EnergyAnalyzer analysis error: %s", e)

    async def _wait_until(self, hour: int, minute: int):
        """Aspetta il prossimo HH:MM. Se già passato oggi, aspetta domani."""
        now    = now_local()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        logger.debug("EnergyAnalyzer: prossimo run %02d:%02d tra %.0f min",
                     hour, minute, wait / 60)
        await asyncio.sleep(wait)

    # ─────────────────────────────────────────────────────────────────────────
    # Snapshot giornaliero

    async def _take_snapshot(self):
        """Legge i valori energetici attuali e li salva per oggi.
        Per sensori cumulativi (>1000 kWh, es. totale da installazione),
        salva il DELTA rispetto allo snapshot di ieri (= produzione del giorno).
        """
        from agent.history_client import _load_energy_sensors
        state_cache = self._state_cache
        sensors = _load_energy_sensors(state_cache)

        today_str = date.today().isoformat()
        from datetime import timedelta as _td
        ieri_str  = (date.today() - _td(days=1)).isoformat()
        ieri_snap = self._history.get(ieri_str, {})

        snap = {}
        for cat, candidates in sensors.items():
            if isinstance(candidates, str):
                candidates = [candidates]
            for eid in candidates:
                s = state_cache.get(eid, {})
                val = s.get("state", "")
                if val and val not in ("unavailable", "unknown"):
                    try:
                        fval = round(float(val), 3)
                        unit = s.get("attributes", {}).get("unit_of_measurement", "")
                        # Sensore cumulativo: valore > 1000 kWh → calcola delta
                        # Confronta con lo snapshot di ieri per trovare la baseline
                        if fval > 1000 and unit in ("kWh", "Wh", ""):
                            ieri_val = ieri_snap.get(cat)
                            if ieri_val is not None and ieri_val > 100:
                                # Delta = oggi - ieri (produzione del giorno)
                                delta = round(fval - ieri_val, 3)
                                snap[cat] = max(0.0, delta)
                                logger.info(
                                    "EnergyAnalyzer snapshot %s [cumulativo] %s: %.3f - %.3f = %.3f kWh",
                                    today_str, cat, fval, ieri_val, snap[cat]
                                )
                            else:
                                # Nessuno snapshot ieri → NON salvare il valore raw
                                # Un sensore cumulativo senza baseline non è utilizzabile.
                                # Salvare il raw (es. 4623 kWh totali dall'installazione)
                                # corromperebbe la media storica.
                                logger.info(
                                    "EnergyAnalyzer snapshot %s [cumulativo, no ieri] %s: SKIP "
                                    "(valore raw %.3f kWh non salvato — aspetto baseline domani)",
                                    today_str, cat, fval
                                )
                                break  # non salvare questo sensore oggi
                        else:
                            snap[cat] = fval
                        break
                    except (ValueError, TypeError):
                        pass

        if not snap:
            logger.warning("EnergyAnalyzer snapshot: nessun valore trovato")
            return

        self._history[today_str] = snap
        await self._save_history()
        logger.info("EnergyAnalyzer snapshot %s: %s", today_str, snap)

    # ─────────────────────────────────────────────────────────────────────────
    # Analisi anomalie

    async def _run_analysis(self):
        """Confronta ieri con la media storica e notifica se anomalo."""
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        yesterday     = self._history.get(yesterday_str)

        if not yesterday:
            logger.info("EnergyAnalyzer: nessun dato per ieri (%s)", yesterday_str)
            return

        # Calcola medie su ultimi HISTORY_DAYS (escluso ieri)
        averages, counts = self._compute_averages(exclude=yesterday_str)

        if not averages or max(counts.values(), default=0) < MIN_HISTORY_DAYS:
            logger.info("EnergyAnalyzer: storico insufficiente (%d giorni), skip analisi", 
                        max(counts.values(), default=0))
            return

        anomalies = self._detect_anomalies(yesterday, averages)

        logger.info("EnergyAnalyzer analisi %s: anomalie=%d", yesterday_str, len(anomalies))

        if not anomalies:
            logger.info("EnergyAnalyzer: nessuna anomalia energetica ieri")
            return

        # Genera messaggio AI
        report = await self._ai_explain(yesterday_str, yesterday, averages, anomalies)

        if report and self.notifier:
            await self.notifier.send_html(report)
            logger.info("EnergyAnalyzer: notifica anomalia inviata")

    def _compute_averages(self, exclude: str = "") -> tuple[dict, dict]:
        """Media dei valori degli ultimi HISTORY_DAYS escludendo 'exclude'."""
        totals: dict = {}
        counts: dict = {}
        # Prendi gli ultimi HISTORY_DAYS in ordine cronologico
        sorted_days = sorted(self._history.keys(), reverse=True)
        relevant = [d for d in sorted_days if d != exclude][:HISTORY_DAYS]

        for day in relevant:
            vals = self._history[day]
            for cat, val in vals.items():
                if val is not None:
                    totals[cat] = totals.get(cat, 0.0) + val
                    counts[cat] = counts.get(cat, 0) + 1

        # Sanity check: per categorie energetiche giornaliere (kWh),
        # valori > 500 kWh sono impossibili in un giorno domestico → outlier da scartare
        MAX_DAILY_KWH = 500.0
        _ENERGY_CATS = {"consumo_casa", "produzione_fv", "rete_enel"}
        averages = {}
        for cat in totals:
            if counts[cat] <= 0:
                continue
            raw_avg = totals[cat] / counts[cat]
            if cat in _ENERGY_CATS and raw_avg > MAX_DAILY_KWH:
                # Media anomala → ricalcola escludendo outlier > 500 kWh
                logger.warning(
                    "EnergyAnalyzer: media %s = %.1f kWh anomala "
                    "— ricalcolo escludendo outlier > %.0f kWh",
                    cat, raw_avg, MAX_DAILY_KWH
                )
                clean_vals = [
                    self._history[d][cat]
                    for d in sorted(self._history.keys(), reverse=True)
                    if d in self._history
                    and cat in self._history[d]
                    and self._history[d][cat] is not None
                    and self._history[d][cat] <= MAX_DAILY_KWH
                ][:HISTORY_DAYS]
                if clean_vals:
                    averages[cat] = round(sum(clean_vals) / len(clean_vals), 3)
                    logger.info(
                        "EnergyAnalyzer: media %s corretta = %.3f kWh (%d giorni validi)",
                        cat, averages[cat], len(clean_vals)
                    )
                # else: nessun dato pulito → non includere nella media
            else:
                averages[cat] = round(raw_avg, 3)
        return averages, counts

    def _detect_anomalies(self, yesterday: dict, averages: dict) -> list[dict]:
        """Confronta ieri vs medie e restituisce lista anomalie."""
        anomalies = []

        CATEGORY_CONFIG = {
            "consumo_casa": {
                "label": "Consumo casa",
                "icon": "🏠",
                "unit": "kWh",
                "high_threshold": THRESHOLD_HIGH,
                "low_threshold": THRESHOLD_LOW,
                "high_severity": "alta",
                "low_severity": "bassa",
            },
            "produzione_fv": {
                "label": "Produzione FV",
                "icon": "☀️",
                "unit": "kWh",
                "high_threshold": 1.50,   # +50% FV non è un problema → ignora
                "low_threshold": THRESHOLD_FV_LOW,
                "high_severity": None,    # None = ignora direzione
                "low_severity": "bassa",
            },
            "rete_enel": {
                "label": "Prelievo rete",
                "icon": "🔌",
                "unit": "kWh",
                "high_threshold": THRESHOLD_HIGH,
                "low_threshold": 0.0,     # sempre positivo → ignora basso
                "high_severity": "alta",
                "low_severity": None,
            },
        }

        for cat, cfg in CATEGORY_CONFIG.items():
            val = yesterday.get(cat)
            avg = averages.get(cat)
            if val is None or avg is None or avg < 0.1:
                continue

            ratio = val / avg

            if cfg["high_severity"] and ratio >= cfg["high_threshold"]:
                anomalies.append({
                    "cat": cat,
                    "label": cfg["label"],
                    "icon": cfg["icon"],
                    "unit": cfg["unit"],
                    "value": val,
                    "average": avg,
                    "ratio": ratio,
                    "direction": "high",
                    "severity": cfg["high_severity"],
                    "delta_pct": round((ratio - 1) * 100),
                })
            elif cfg["low_severity"] and ratio <= cfg["low_threshold"] and val > 0.05:
                anomalies.append({
                    "cat": cat,
                    "label": cfg["label"],
                    "icon": cfg["icon"],
                    "unit": cfg["unit"],
                    "value": val,
                    "average": avg,
                    "ratio": ratio,
                    "direction": "low",
                    "severity": cfg["low_severity"],
                    "delta_pct": round((1 - ratio) * 100),
                })

        # Anomalia autosufficienza: produzione buona ma consumo alto
        fv  = yesterday.get("produzione_fv", 0)
        con = yesterday.get("consumo_casa", 0)
        avg_fv  = averages.get("produzione_fv", 0)
        avg_con = averages.get("consumo_casa", 0)
        if fv > 0.5 and con > 0.5 and avg_fv > 0.5 and avg_con > 0.5:
            self_suff_now = min(100, round(fv / con * 100))
            self_suff_avg = min(100, round(avg_fv / avg_con * 100))
            if self_suff_now < self_suff_avg * 0.65:  # -35% autosufficienza
                anomalies.append({
                    "cat": "autosufficienza",
                    "label": "Autosufficienza",
                    "icon": "📊",
                    "unit": "%",
                    "value": self_suff_now,
                    "average": self_suff_avg,
                    "ratio": self_suff_now / self_suff_avg,
                    "direction": "low",
                    "severity": "bassa",
                    "delta_pct": round(self_suff_avg - self_suff_now),
                })

        return anomalies

    # ─────────────────────────────────────────────────────────────────────────
    # AI explain

    async def _ai_explain(
        self,
        day_str: str,
        yesterday: dict,
        averages: dict,
        anomalies: list[dict],
    ) -> Optional[str]:
        """Usa l'AI per spiegare le anomalie in modo leggibile."""

        # Costruisci il contesto testuale per l'AI
        day_label = datetime.fromisoformat(day_str).strftime("%A %d %B")
        anom_text = "\n".join(
            f"- {a['icon']} {a['label']}: {a['value']} {a['unit']} "
            f"({'+'if a['direction']=='high' else '-'}{a['delta_pct']}% rispetto alla media {a['average']} {a['unit']})"
            for a in anomalies
        )

        all_vals = "\n".join(
            f"- {cat}: {val} kWh (media: {averages.get(cat, '?')} kWh)"
            for cat, val in yesterday.items()
        )

        system = (
            "Sei HomeMind, assistente AI per la domotica. "
            "Analizza i dati energetici e spiega le anomalie in modo chiaro e utile. "
            "Sii conciso (3-5 righe), usa emoji, suggerisci possibili cause pratiche. "
            "Evita tecnicismi. Rispondi in italiano."
        )

        user = (
            f"Ieri ({day_label}) ho rilevato anomalie energetiche in casa:\n\n"
            f"ANOMALIE:\n{anom_text}\n\n"
            f"TUTTI I VALORI DI IERI:\n{all_vals}\n\n"
            f"Spiega brevemente cosa potrebbe essere successo e suggerisci 1-2 azioni. "
            f"Inizia direttamente con l'analisi, senza introduzioni."
        )

        try:
            explanation = await self.ai.ask(system, user, max_tokens=300)
        except Exception as e:
            logger.warning("EnergyAnalyzer AI explain error: %s", e)
            explanation = None

        # Costruisci messaggio Telegram formattato
        lines = [
            f"📊 <b>Anomalia Energetica — {day_label}</b>",
            "─" * 20,
        ]

        for a in anomalies:
            arrow = "⬆️" if a["direction"] == "high" else "⬇️"
            lines.append(
                f"{a['icon']} {arrow} <b>{a['label']}:</b> {a['value']} {a['unit']} "
                f"({'+' if a['direction'] == 'high' else '-'}{a['delta_pct']}% vs media {a['average']} {a['unit']})"
            )

        lines.append("")
        if explanation:
            lines.append(f"🤖 <i>{explanation.strip()}</i>")
        else:
            lines.append("⚠️ <i>Analisi AI non disponibile</i>")

        lines.append("")
        lines.append(f"<i>📅 Storico: {len(self._history)} giorni registrati</i>")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Metodo pubblico: analisi on-demand (da Telegram /energia_analisi)

    async def analyze_on_demand(self, period_days: int = 7) -> str:
        """
        Analisi energetica completa degli ultimi N giorni.
        Chiamata da Telegram o dalla web dashboard.
        """
        if len(self._history) < 2:
            return (
                "📊 <b>Analisi Energetica</b>\n\n"
                "⚠️ Storico insufficiente — HomeMind inizia a raccogliere dati ogni sera alle 23:30.\n"
                f"Attualmente: <b>{len(self._history)} giorni</b> registrati su {HISTORY_DAYS} necessari."
            )

        sorted_days = sorted(self._history.keys(), reverse=True)
        recent = sorted_days[:period_days]
        averages, counts = self._compute_averages()

        # Trova giorni con anomalie
        anomaly_days = []
        for day in recent:
            vals = self._history[day]
            anomalies = self._detect_anomalies(vals, averages)
            if anomalies:
                anomaly_days.append((day, anomalies))

        lines = [f"📊 <b>Analisi Energia — ultimi {len(recent)} giorni</b>", "─" * 20]

        # Tabella riepilogativa
        lines.append("📅 <b>Storico recente:</b>")
        ICONS = {"consumo_casa": "🏠", "produzione_fv": "☀️", "rete_enel": "🔌", "batteria_wh": "🔋"}
        for day in recent[:7]:
            vals = self._history[day]
            day_label = datetime.fromisoformat(day).strftime("%d/%m")
            parts = []
            for cat, icon in ICONS.items():
                v = vals.get(cat)
                if v is not None:
                    avg = averages.get(cat)
                    marker = ""
                    if avg and avg > 0.1:
                        ratio = v / avg
                        if ratio >= THRESHOLD_HIGH:
                            marker = "⬆️"
                        elif ratio <= THRESHOLD_LOW:
                            marker = "⬇️"
                    parts.append(f"{icon}{marker}{v:.1f}")
            lines.append(f"  <code>{day_label}</code>  " + "  ".join(parts))

        # Medie
        lines.append("")
        lines.append("📊 <b>Medie periodo:</b>")
        for cat, icon in ICONS.items():
            avg = averages.get(cat)
            if avg is not None:
                lines.append(f"  {icon} {avg:.2f} kWh/giorno ({counts.get(cat,0)} giorni)")

        # Giorni anomali
        if anomaly_days:
            lines.append("")
            lines.append(f"⚠️ <b>Giorni anomali ({len(anomaly_days)}/{len(recent)}):</b>")
            for day, anomalies in anomaly_days[:5]:
                day_label = datetime.fromisoformat(day).strftime("%d/%m")
                anoms = ", ".join(
                    f"{a['icon']}{'+' if a['direction']=='high' else '-'}{a['delta_pct']}%"
                    for a in anomalies
                )
                lines.append(f"  📅 {day_label}: {anoms}")
        else:
            lines.append("")
            lines.append("✅ <b>Nessuna anomalia</b> negli ultimi giorni")

        lines.append("")
        lines.append(f"<i>🗂️ {len(self._history)} giorni in archivio · ⬆️=alto ⬇️=basso vs media</i>")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza storico

    async def _load_history(self):
        """Carica lo storico energetico dal file JSON."""
        try:
            if HISTORY_PATH.exists():
                data = json.loads(HISTORY_PATH.read_text())
                # Tieni solo gli ultimi HISTORY_DAYS
                sorted_keys = sorted(data.keys(), reverse=True)[:HISTORY_DAYS]
                self._history = {k: data[k] for k in sorted_keys}
                logger.info("EnergyAnalyzer: caricati %d giorni di storico", len(self._history))
            else:
                self._history = {}
                logger.info("EnergyAnalyzer: nessuno storico esistente, parto da zero")
        except Exception as e:
            logger.warning("EnergyAnalyzer load history error: %s", e)
            self._history = {}

    async def _save_history(self):
        """Salva lo storico energetico su file JSON."""
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Tieni solo ultimi HISTORY_DAYS
            sorted_keys = sorted(self._history.keys(), reverse=True)[:HISTORY_DAYS]
            to_save = {k: self._history[k] for k in sorted_keys}
            HISTORY_PATH.write_text(json.dumps(to_save, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning("EnergyAnalyzer save history error: %s", e)

    def get_history_summary(self) -> dict:
        """Ritorna un riassunto dello storico per la dashboard."""
        averages, counts = self._compute_averages()
        return {
            "days_recorded": len(self._history),
            "averages": averages,
            "counts": counts,
            "latest_date": max(self._history.keys()) if self._history else None,
        }
