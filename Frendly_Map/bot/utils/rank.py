# bot/utils/rank.py
def get_user_rank_display(pts: int) -> str:
    if pts >= 500:
        return "👑 МАСТЕР КАРТОГРАФ"
    elif pts >= 300:
        return "🗿 КАРТОГРАФ"
    elif pts >= 200:
        return "⛰️ ПЕРВООТКРЫВАТЕЛЬ 1"
    elif pts >= 100:
        return "⛰️ ПЕРВООТКРЫВАТЕЛЬ 2"
    elif pts >= 0:
        return "⛰️ ПЕРВООТКРЫВАТЕЛЬ 3"
    elif pts >= -100:
        return "🗺️ ПУТЕШЕСТВЕННИК 3"
    elif pts >= -200:
        return "🗺️ ПУТЕШЕСТВЕННИК 2"
    elif pts >= -300:
        return "🗺️ ПУТЕШЕСТВЕННИК 1"
    elif pts >= -400:
        return "🌍 ИССЛЕДОВАТЕЛЬ 3"
    elif pts >= -500:
        return "🌍 ИССЛЕДОВАТЕЛЬ 2"
    else:
        return "🌍 ИССЛЕДОВАТЕЛЬ 1"


def get_rank_title(pts: int) -> str:
    return get_user_rank_display(pts)
