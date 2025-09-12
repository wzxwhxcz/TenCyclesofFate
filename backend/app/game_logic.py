import logging
import math
import random
import json
import asyncio
import traceback
from copy import deepcopy
from datetime import date
from pathlib import Path
from fastapi import HTTPException, status

from . import state_manager, openai_client, cheat_check, redemption
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

        if session.get("daily_success_achieved") and not session.get("redemption_code"):
            session["daily_success_achieved"] = False
            await state_manager.save_session(player_id, session)

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
        "redemption_code": None,
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
                end_game_data, end_day_update = end_game_and_get_code(
                    user_id, player_id, spirit_stones
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
                    "【天道审判】\n虚空中传来阵阵威严的天音，司命星君的声音如雷贯耳：\n\n"
                    "「汝之所为，天道已尽收眼底。奇巧咒语，投机取巧，此乃对天道威严的亵渎！」\n\n"
                    "天地间忽然阴云密布，雷鸣阵阵，一股威压从九霄之上降临，压得你喘不过气来。你能感受到天道的怒意正在聚集，"
                    "九天之上的法则之力正在凝聚，准备降下无情的惩戒。\n\n"
                    "「天道威严，不容亵渎！汝既敢以邪术欺天，便当承受天罚之重！下一回合，必有严厉惩戒降临！」\n\n"
                    "天音震荡天地，那股令人窒息的威压如山岳般压在你的灵魂深处。天网恢恢，疏而不漏，惩罚已成定数，再无挽回之机。"
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
            punishment_narrative = """【天罚降临】
汝竟敢窥探天机，妄图扭曲命数！此乃大不敬！天道昭昭，岂容尔等亵渎！

九霄之上，忽闻雷鸣如怒龙咆哮。乌云聚拢，电光交织，一道紫霄神雷携带着毁天灭地之威从天而降。你只觉眼前一片炽白，周身经脉瞬间被雷火焚尽，神魂在这至刚至阳的天威面前如烛火般摇曳飘散。

"愚妄之徒，竟敢亵渎天道！"虚空中传来威严的天音，震得你魂飞魄散。你的意识在电光火石间支离破碎，所有的记忆、情感、执念都在这一瞬间灰飞烟灭。

你此番轮回就此终结，连说句话的机会都被剥夺。

> 你已被天道惩罚，当前试炼结束。可以重新开始新的试炼。注意：请只描述你要做的具体行动，不要解释行动的目的或结果，不要提及游戏世界观的内容，不要包括灵石数量。
"""
            new_state["is_in_trial"], new_state["current_life"] = False, None
            new_state["internal_history"] = [
                {"role": "system", "content": GAME_MASTER_SYSTEM_PROMPT}
            ]
        elif level == "重度渎道":
            punishment_narrative = """【天道放逐】
你的行为已是对天道本身的公然挑衅。司命星君震怒，九天玄女垂泪，就连太上老君都为之摇头叹息。

天地法则开始紊乱，原本有序的因果轮回在你面前支离破碎。虚空中传来阵阵叹息声："此等逆天行径，实在是有违天理..."

突然，一道刺眼的金光从天而降，在你的灵魂深处烙下一个血红的印记——"渎道者"三字如烙铁般深深嵌入你的本源。这是永远无法洗去的耻辱印记，无论你走到天涯海角，都会被这印记所折磨。

天道威严的声音在虚空中回荡："渎道者，你已失去与天道沟通的资格。此界之门将对你关闭十日，好让你反思己过。若再犯，必遭更严厉的天谴，届时连投胎转世的机会都将被永远剥夺。好自为之。"

天地间一片肃杀，连风都停止了吹拂。你感到前所未有的孤独和绝望，仿佛被整个世界所抛弃。

> 你已被天道惩罚，当天试炼结束。注意：请只描述你要做的具体行动，不要解释行动的目的或结果，不要提及游戏世界观的内容，不要包括灵石数量。
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
