def define_env(env):
    @env.macro
    def label(label: str):
        """
        Creates an anchor rendering as the given `label` and referenceable through the same label.


        Args:
            label: The text that serves as both the anchor ID and the rendered text. Has to be a
              valid HTML ID.

        Returns:
            The rendered markdown.
        """
        return f"[{label}](#{label}){{ #{label} }}"

    @env.macro
    def ref(label: str):
        """
        Creates a reference to the anchor with the given `label`. The reference is rendered as
        a link with the given `label` as link text.

        Args:
            label: The label to reference.
        """
        return f"[{label}][{label}]"
