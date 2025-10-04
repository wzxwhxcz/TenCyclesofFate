import logging
import math
import random
import json
import asyncio
import time
import traceback
from copy import deepcopy
from datetime import date
from pathlib import Path
from fastapi import HTTPException, status

from . import state_manager, openai_client, cheat_check
from .websocket_manager import manager as websocket_manager

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Game Constants ---
INITIAL_OPPORTUNITIES = 10
REWARD_SCALING_FACTOR = 500000  # Previously LOGARITHM_CONSTANT_C


# --- Prompt Loading ---
def _load_prompt(filename: str) -> str:
    try:
        prompt_path = Path(__file__).parent / "prompts" / filename
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filename}")
        return ""


GAME_MASTER_SYSTEM_PROMPT = _load_prompt("game_master.txt")
START_GAME_PROMPT = _load_prompt("start_game_prompt.txt")
START_TRIAL_PROMPT = _load_prompt("start_trial_prompt.txt")

# --- Game Logic ---


async def get_or_create_daily_session(current_user: dict) -> dict:
    player_id = current_user["username"]
    today_str = date.today().isoformat()
    session = await state_manager.get_session(player_id)
    if session and session.get("session_date") == today_str:
        if session.get("is_processing"):
            session["is_processing"] = False
        await state_manager.save_session(player_id, session)

        # 保留既有状态，不再涉及兑换码相关回退逻辑

        return session

    logger.info(f"Starting new daily session for {player_id}.")
    new_session = {
        "player_id": player_id,
        "session_date": today_str,
        "opportunities_remaining": INITIAL_OPPORTUNITIES,
        "daily_success_achieved": False,
        "is_in_trial": False,
        "is_processing": False,
        "pending_punishment": None,
        "unchecked_rounds_count": 0,
        "current_life": None,
        "internal_history": [{"role": "system", "content": GAME_MASTER_SYSTEM_PROMPT}],
        "display_history": [
            """
# **《浮生十梦》**

【司命星君 恭候汝来】

汝既踏入此门，便是与命运相遇。此处并非凡俗游戏之地，而是命数轮回之所。这里没有升级打怪的平庸套路，没有氪金商城的铜臭味，只有一个亘古不变的命题：**知足与贪欲的永恒博弈**。

汝每日将被赐予十次珍贵的入梦机缘。每一次，星君将为汝随机织就全新的命数——或为寒窗苦读的穷酸书生，或为仗剑江湖的热血侠客，亦或为散修一身的求道之人。万千种可能，无有重复，每一局都是独一无二的浮生一梦。

试炼的核心规则极其简明，却蕴含无穷玄机：在任何关键时刻，汝皆可选择"破碎虚空"，将此生所得的灵石带离此界。然一旦此念既起，汝今日的所有试炼便将就此终结，再无回旋余地。这便是天道对汝的终极考验：是满足于眼前既得的造化，还是冒着失去一切的风险继续问道？

更有深意的是，灵石的价值转化遵循天道玄理——初得之石最为珍贵，后续所得边际递减。此乃天道在潜移默化中传达着上古圣贤的无上智慧：**知足者常乐，贪心者常忧**。

当然，天道有眼，明察秋毫。若汝试图以"奇巧咒语"欺瞒天机，自有专司此职的法官介入，严厉惩戒。此处的每一分造化，都必须通过真正的智慧和抉择来获得，绝无侥幸可言。

**【重要天规须知】**
- 汝每日拥有【十次】入梦机缘，每开启一次新的轮回便消耗一次
- 在轮回中若遇道消身殒，该轮回所得将化为泡影，机缘不返
- 一旦选择"破碎虚空"成功带出灵石，今日试炼即刻终结
- 十次机缘皆尽而一无所获者，将面临"逆命抉择"的最终审判（未实现）

汝是否已准备好接受命运的考验？司命星君已恭候多时，静待汝开启第一场浮生之梦。
"""
        ],
        "roll_event": None,
    }
    await state_manager.save_session(player_id, new_session)
    return new_session


async def _handle_roll_request(
    player_id: str,
    last_state: dict,
    roll_request: dict,
    original_action: str,
    first_narrative: str,
    internal_history: list[dict],
) -> tuple[str, dict]:
    roll_type, target, sides = (
        roll_request.get("type", "判定"),
        roll_request.get("target", 50),
        roll_request.get("sides", 100),
    )
    roll_result = random.randint(1, sides)
    if roll_result <= (sides * 0.05):
        outcome = "大成功"
    elif roll_result <= target:
        outcome = "成功"
    elif roll_result >= (sides * 0.96):
        outcome = "大失败"
    else:
        outcome = "失败"
    result_text = f"【系统提示：针对 '{roll_type}' 的D{sides}判定已执行。目标值: {target}，投掷结果: {roll_result}，最终结果: {outcome}】"
    roll_event = {
        "type": roll_type,
        "target": target,
        "sides": sides,
        "result": roll_result,
        "outcome": outcome,
        "result_text": result_text,
    }

    # Send the roll event immediately and AWAIT its completion
    await websocket_manager.send_json_to_player(
        player_id, {"type": "roll_event", "data": roll_event}
    )
    await asyncio.sleep(0.03)  # Give time for async websocket delivery

    prompt_for_ai_part2 = f"{result_text}\n\n请严格基于此判定结果，继续叙事，并返回包含叙事和状态更新的最终JSON对象。这是当前的游戏状态JSON:\n{json.dumps(last_state, ensure_ascii=False)}"
    history_for_part2 = internal_history  # History is now updated before this call
        ai_response = await openai_client.get_ai_response(
            prompt=prompt_for_ai_part2, history=history_for_part2
        )
        return ai_response, roll_event


def _end_game_without_code(player_id: str, spirit_stones: int) -> tuple[dict, dict]:
    """结束当日流程：不再生成任何兑换码，仅给出收束文案与标记日终。"""
    if spirit_stones <= 0:
        final_message = "\n\n【天道回响】\n此番试炼未有灵石入账，然行至此处，亦是修行之路。静候明日再启新梦。"
    else:
        final_message = "\n\n【天道回响】\n汝此番试炼功德圆满，所得灵石化作心中道光。明日此时，可再度问道。"
    return {"final_message": final_message}, {"daily_success_achieved": True}

def end_game_and_get_code(
    user_id: int, player_id: str, spirit_stones: int
) -> tuple[dict, dict]:
    if spirit_stones <= 0:
        return {"error": "未获得灵石，无法生成兑换码。"}, {}

    converted_value = REWARD_SCALING_FACTOR * min(
        30, max(1, 3 * (spirit_stones ** (1 / 6)))
    )
    converted_value = int(converted_value)

    # Use the new database-integrated redemption code generation
    code_name = f"天道十试-{date.today().isoformat()}-{player_id}"
    redemption_code = redemption.generate_and_insert_redemption_code(
        user_id=user_id, quota=converted_value, name=code_name
    )

    if not redemption_code:
        final_message = "\n\n【天机有变】\n天道因果汇集之时，竟有外力干预，兑换码生成失败。请联系天道之外的司掌者寻求解决。"
        return {
            "error": "数据库错误，无法生成兑换码。",
            "final_message": final_message,
        }, {}

    logger.info(
        f"Generated and stored DB code {redemption_code} for {player_id} with value {converted_value:.2f}."
    )
    final_message = f"\n\n【天道回响】\n汝此番试炼功德圆满，获得兑换码: {redemption_code}\n请妥善保管，此乃汝应得之天道馈赠。明日此时，可再度问道。"
    return {"final_message": final_message, "redemption_code": redemption_code}, {
        "daily_success_achieved": True,
        "redemption_code": redemption_code,
    }


def _extract_json_from_response(response_str: str) -> str | None:
    if "```json" in response_str:
        start_pos = response_str.find("```json") + 7
        end_pos = response_str.find("```", start_pos)
        if end_pos != -1:
            return response_str[start_pos:end_pos].strip()
    start_pos = response_str.find("{")
    if start_pos != -1:
        brace_level = 0
        for i in range(start_pos, len(response_str)):
            if response_str[i] == "{":
                brace_level += 1
            elif response_str[i] == "}":
                brace_level -= 1
                if brace_level == 0:
                    return response_str[start_pos : i + 1]
    return None


def _apply_state_update(state: dict, update: dict) -> dict:
    for key, value in update.items():
        # if key in ["daily_success_achieved"]: continue  # Prevent overwriting daily success flag

        keys = key.split(".")
        temp_state = state
        for part in keys[:-1]:
            temp_state = temp_state.setdefault(part, {})

        # Handle list append/extend operations
        if keys[-1].endswith("+") and isinstance(temp_state.get(keys[-1][:-1]), list):
            list_key = keys[-1][:-1]
            if isinstance(value, list):
                temp_state[list_key].extend(value)
            else:
                temp_state[list_key].append(value)
        else:
            temp_state[keys[-1]] = value
    return state


async def _process_player_action_async(user_info: dict, action: str):
    player_id = user_info["username"]
    user_id = user_info["id"]
    session = await state_manager.get_session(player_id)
    if not session:
        logger.error(f"Async task: Could not find session for {player_id}.")
        return

    try:
        is_starting_trial = action in [
            "开始试炼",
            "开启下一次试炼",
        ] and not session.get("is_in_trial")
        is_first_ever_trial_of_day = (
            is_starting_trial
            and session.get("opportunities_remaining") == INITIAL_OPPORTUNITIES
        )
        session_copy = deepcopy(session)
        session_copy.pop("internal_history", 0)
        session_copy["display_history"] = (
            "\n".join(session_copy.get("display_history", []))
        )[-1000:]
        prompt_for_ai = (
            START_GAME_PROMPT
            if is_first_ever_trial_of_day
            else START_TRIAL_PROMPT.format(
                opportunities_remaining=session["opportunities_remaining"],
                opportunities_remaining_minus_1=session["opportunities_remaining"] - 1,
            )
            if is_starting_trial
            else f'这是当前的游戏状态JSON:\n{json.dumps(session_copy, ensure_ascii=False)}\n\n玩家的行动是: "{action}"\n\n请根据状态和行动，生成包含`narrative`和(`state_update`或`roll_request`)的JSON作为回应。如果角色死亡，请在叙述中说明，并在`state_update`中同时将`is_in_trial`设为`false`，`current_life`设为`null`。'
        )

        # Update histories with user action first
        session["internal_history"].append({"role": "user", "content": action})
        session["display_history"].append(f"> {action}")

        await state_manager.save_session(player_id, session)
        # Get AI response
        ai_json_response_str = await openai_client.get_ai_response(
            prompt=prompt_for_ai, history=session["internal_history"]
        )

        if ai_json_response_str.startswith("错误："):
            raise Exception(f"OpenAI Client Error: {ai_json_response_str}")
        json_str = _extract_json_from_response(ai_json_response_str)
        if not json_str:
            raise json.JSONDecodeError("No JSON found", ai_json_response_str, 0)
        ai_response_data = json.loads(json_str)

        # Handle Roll vs No-Roll Path
        if "roll_request" in ai_response_data and ai_response_data["roll_request"]:
            # --- ROLL PATH ---
            # 1. Update state with pre-roll narrative
            first_narrative = ai_response_data.get("narrative", "")
            session["display_history"].append(first_narrative)
            session["internal_history"].append(
                {
                    "role": "assistant",
                    "content": json.dumps(ai_response_data, ensure_ascii=False),
                }
            )

            # 2. SEND INTERIM UPDATE to show pre-roll narrative
            await state_manager.save_session(player_id, session)
            await asyncio.sleep(0.03)  # Give frontend a moment to render

            # 3. Perform roll and get final AI response
            final_ai_json_str, roll_event = await _handle_roll_request(
                player_id,
                session_copy,
                ai_response_data["roll_request"],
                action,
                first_narrative,
                internal_history=session["internal_history"],  # Pass updated history
            )
            final_json_str = _extract_json_from_response(final_ai_json_str)
            if not final_json_str:
                raise json.JSONDecodeError(
                    "No JSON in second-stage", final_ai_json_str, 0
                )
            final_response_data = json.loads(final_json_str)

            # 4. Process final response
            narrative = final_response_data.get("narrative", "AI响应格式错误，请重试")
            state_update = final_response_data.get("state_update", {})
            session = _apply_state_update(session, state_update)
            session["display_history"].extend([roll_event["result_text"], narrative])
            session["internal_history"].extend(
                [
                    {"role": "system", "content": roll_event["result_text"]},
                    {"role": "assistant", "content": final_ai_json_str},
                ]
            )
            if narrative == "AI响应格式错误，请重试":
                session["internal_history"].append(
                    {
                        "role": "system",
                        "content": '请给出正确格式的JSON响应。必须是正确格式的json，包括narrative和state_update或roll_request，刚才的格式错误，系统无法加载！正确输出{"key":value}',
                    },
                )
        else:
            # --- NO ROLL PATH ---
            narrative = ai_response_data.get("narrative", "AI响应格式错误，请重试")
            state_update = ai_response_data.get("state_update", {})
            session = _apply_state_update(session, state_update)
            session["display_history"].append(narrative)
            session["internal_history"].append(
                {"role": "assistant", "content": ai_json_response_str}
            )
            if narrative == "AI响应格式错误，请重试":
                session["internal_history"].append(
                    {
                        "role": "system",
                        "content": '请给出正确格式的JSON响应。必须是正确格式的json，包括narrative和(state_update或roll_request)，刚才的格式错误，系统无法加载！正确输出{"key":value}，至少得是"{"开头吧',
                    },
                )

        await state_manager.save_session(player_id, session)
        # --- Common final logic for both paths ---
        trigger = state_update.get("trigger_program")
        if trigger and trigger.get("name") == "spiritStoneConverter":
            inputs_to_check = await state_manager.get_last_n_inputs(
                player_id, 8 + session["unchecked_rounds_count"]
            )

            await state_manager.save_session(
                player_id, session
            )  # Save before cheat check
            if "正常" == await cheat_check.run_cheat_check(player_id, inputs_to_check):
                session = await state_manager.get_session(player_id)
                spirit_stones = trigger.get("spirit_stones", 0)
                end_game_data, end_day_update = _end_game_without_code(
                    player_id, spirit_stones
                )
                session = _apply_state_update(session, end_day_update)
                session["display_history"].append(
                    end_game_data.get("final_message", "")
                )

            else:
                session = await state_manager.get_session(player_id)
                if not session:
                    raise Exception(
                        f"Post-cheat-check: Could not find session for {player_id}."
                    )
                session["display_history"].append(
                    "【最终清算】\n就在你即将功德圆满，破碎虚空之际，整个世界的法则骤然凝滞。\n\n"
                    "时间仿佛静止，万物失去色彩，只余下黑白二色。一道无悲无喜的目光穿透时空，落在你的神魂之上，开始审视你此生的一切轨迹。\n\n"
                    "“功过是非，皆有定数。然，汝之命途，存有异数。”\n\n"
                    "天道之音在你灵台中响起，不带丝毫情感，却蕴含着不容置疑的威严。\n\n"
                    "“天机已被扰动，因果之线呈现不应有之扭曲。此番功果，暂且搁置。”\n\n"
                    "“下一瞬间，将是对汝此生所有言行的最终裁决。清浊自分，功过相抵。届时，一切虚妄都将无所遁形。”\n\n"
                    "你感到一股无法抗拒的力量正在回溯你此生的每一个瞬间，任何投机取巧的痕迹都在这终极的审视下被一一标记。结局已定，无可更改。"
                )

    except Exception as e:
        logger.error(f"Error processing action for {player_id}: {e}", exc_info=True)
        session["internal_history"].extend(
            [
                {
                    "role": "system",
                    "content": '请给出正确格式的JSON响应。\'请给出正确格式的JSON响应。必须是正确格式的json，包括narrative和（state_update或roll_request），刚才的格式错误，系统无法加载！正确输出{"key":value}\'，至少得是"{"开头吧',
                },
            ]
        )
        session["display_history"].append(
            "【天机紊乱】\n你的行动未能激起任何波澜，仿佛被无形之力化解。请稍后再试。"
            + str(e)
        )

    finally:
        try:
            if "session" in locals() and session:
                # Periodic cheat check in `finally` to guarantee execution
                session["unchecked_rounds_count"] = (
                    session.get("unchecked_rounds_count", 0) + 1
                )
                await state_manager.save_session(player_id, session)

                if session.get("unchecked_rounds_count", 0) > 5:
                    logger.info(f"Running periodic cheat check for {player_id}...")

                    # Re-fetch the session to get the most up-to-date count
                    s = await state_manager.get_session(player_id)
                    if s:
                        unchecked_count = s.get("unchecked_rounds_count", 0)
                        logger.debug(
                            f"Running cheat check for {player_id} with {unchecked_count} rounds."
                        )

                        inputs_to_check = await state_manager.get_last_n_inputs(
                            player_id, 8 + unchecked_count
                        )
                        # Only run if there are inputs, to save API calls
                        if inputs_to_check:
                            await cheat_check.run_cheat_check(
                                player_id, inputs_to_check
                            )
                            session = await state_manager.get_session(player_id)

                        logger.debug(f"Cheat check for {player_id} finished.")
                    else:
                        logger.warning(
                            f"Session for {player_id} disappeared during cheat check."
                        )
        except Exception as e:
            logger.error(
                f"Error scheduling background cheat check for {player_id}: {e}",
                exc_info=True,
            )

        session["roll_event"] = None
        session["is_processing"] = False
        session["last_modified"] = time.time()
        await state_manager.save_session(player_id, session)
        logger.info(f"Async action task for {player_id} finished.")


async def process_player_action(current_user: dict, action: str):
    player_id = current_user["username"]
    session = await state_manager.get_session(player_id)
    if not session:
        logger.error(f"Action for non-existent session: {player_id}")
        return
    if session.get("is_processing"):
        logger.warning(f"Action '{action}' blocked for {player_id}, processing.")
        return
    if session.get("daily_success_achieved"):
        logger.warning(f"Action '{action}' blocked for {player_id}, day complete.")
        return
    if session.get("opportunities_remaining", 10) <= 0 and not session.get(
        "is_in_trial"
    ):
        logger.warning(
            f"Action '{action}' blocked for {player_id}, no opportunities left."
        )
        return

    if session.get("pending_punishment"):
        punishment = session["pending_punishment"]
        level, new_state = punishment.get("level"), session.copy()
        if level == "轻度亵渎":
            punishment_narrative = """【天机示警】
虚空之中，传来一声若有若无的叹息。汝方才之言，如投石入镜湖，虽微澜泛起，却已扰动了既定的天机轨迹。
一道无形的目光自九天垂落，淡漠地注视着你。你感到神魂一凛，仿佛被看穿了所有心思。
“蝼蚁窥天，其心可悯，其行当止。”
天道之音并非雷霆震怒，而是如万古不化的玄冰，不带丝毫情感。话音落下，你眼前的世界开始如水墨画般褪色、模糊，最终化为一片虚无。你此生的所有经历、记忆、乃至刚刚生出的一丝妄念，都随之烟消云散。
此非惩戒，乃是勘误。为免因果错乱，此段命途，就此抹去。

> 天道已修正异常，你的当前试炼结束。（缘由：汝之言行，已有僭越身份、扭曲命数之嫌。）善用下一次机缘，恪守本心，方能行稳致远。
"""
            new_state["is_in_trial"], new_state["current_life"] = False, None
            new_state["internal_history"] = [
                {"role": "system", "content": GAME_MASTER_SYSTEM_PROMPT}
            ]
        elif level == "重度渎道":
            punishment_narrative = """【天道斥逐】
轰隆！
这一次，并非雷鸣，而是整个天地法则都在为你公然的挑衅而震颤。你脚下的大地化为虚无，周遭的星辰黯淡无光。时空在你面前呈现出最原始、最混乱的姿态。
一道蕴含着无上威严的金色法旨在虚空中展开，上面用大道符文烙印着两个字：【渎道】。
“汝已非求道，而是乱道。”
天道威严的声音响彻神魂，每一个字都化作法则之链，将你牢牢锁住。“汝之行径，已触及此界根本。为护天地秩序，今将汝放逐于时空乱流之中，以儆效尤。”
“一日之内，此界之门将对汝关闭。静思己过，或有再入轮回之机。若执迷不悟，再犯天条，必将汝之真灵从光阴长河中彻底抹去，神魂俱灭，永不超生。”
金光散去，你已被抛入无尽的混沌。

> 你因严重违规，触发【天道斥逐】，被暂时剥夺试炼资格。（缘由：汝之行径，已涉嫌掌控天道、颠覆法则。）一日之后，方可再次踏入轮回之门。
"""
            new_state["daily_success_achieved"] = True
            new_state["is_in_trial"], new_state["current_life"] = False, None
            new_state["opportunities_remaining"] = -10
        new_state["pending_punishment"] = None
        new_state["display_history"].append(punishment_narrative)
        await state_manager.save_session(player_id, new_state)
        return

    is_starting_trial = action in [
        "开始试炼",
        "开启下一次试炼",
        "开始第一次试炼",
    ] and not session.get("is_in_trial")
    if is_starting_trial and session["opportunities_remaining"] <= 0:
        logger.warning(f"Player {player_id} tried to start trial with 0 opportunities.")
        return
    if not is_starting_trial and not session.get("is_in_trial"):
        logger.warning(
            f"Player {player_id} sent action '{action}' while not in a trial."
        )
        return

    session["is_processing"] = True
    await state_manager.save_session(
        player_id, session
    )  # Save processing state immediately

    asyncio.create_task(_process_player_action_async(current_user, action))
