from app.tools.loader import registry


class ToolSelector:

    def select(self, user_input: str):

        text = user_input.lower()

        best_tool = None

        best_score = 0

        for tool in registry.tools.values():

            score = 0

            for keyword in tool.manifest.keywords:

                if keyword in text:
                    score += 1

            if score > best_score:

                best_score = score

                best_tool = tool

        return best_tool