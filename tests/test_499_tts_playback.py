"""
Tests for #499: TTS playback of agent responses via Web Speech API.

Verifies that TTS utility functions, speaker button rendering, and
settings controls are present in the WebUI codebase.
"""
import os
import re

STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'static')


def _read(filename):
    return open(os.path.join(STATIC_DIR, filename), encoding='utf-8').read()


class TestTtsUtilityFunctions:
    """TTS core functions exist in ui.js."""

    def test_strip_for_tts_exists(self):
        src = _read('ui.js')
        assert 'function _stripForTTS(' in src, \
            "_stripForTTS function not found in ui.js"

    def test_speak_message_exists(self):
        src = _read('ui.js')
        assert 'function speakMessage(' in src, \
            "speakMessage function not found in ui.js"

    def test_stop_tts_exists(self):
        src = _read('ui.js')
        assert 'function stopTTS(' in src, \
            "stopTTS function not found in ui.js"

    def test_auto_read_exists(self):
        src = _read('ui.js')
        assert 'function autoReadLastAssistant(' in src, \
            "autoReadLastAssistant function not found in ui.js"

    def test_strip_code_blocks(self):
        """_stripForTTS must remove ``` code blocks."""
        src = _read('ui.js')
        assert re.search(r'_stripForTTS.*```', src, re.DOTALL), \
            "_stripForTTS must handle fenced code blocks"

    def test_code_block_speaks_audible_cue(self):
        """_stripForTTS must replace code blocks with a spoken cue, not silence.

        Previously code blocks collapsed to a bare space, so the listener heard
        an unexplained gap. They should now hear a short cue pointing them to the
        screen. See the 'audible code-block cue' change.
        """
        src = _read('ui.js')
        # The fenced-code replacement target must contain the spoken cue text.
        assert 'code block' in src and 'see screen' in src, \
            "_stripForTTS must emit an audible '(code block — see screen)' cue"
        # Guard against regressing to the silent ' ' replacement on the fenced regex.
        m = re.search(r"text=text\.replace\(/\(\^\|\\n\).*?```.*?/g,\s*'([^']*)'\)", src)
        assert m, "fenced code-block replace() line not found in _stripForTTS"
        assert m.group(1).strip() not in ('', '.'), \
            "fenced code block must not collapse to silent whitespace — use the cue"

    def test_strip_media_paths(self):
        """_stripForTTS must replace MEDIA: paths."""
        src = _read('ui.js')
        assert 'MEDIA:' in src and 'a file' in src, \
            "_stripForTTS must replace MEDIA: paths"

    def test_uses_speech_synthesis(self):
        """speakMessage must use window.speechSynthesis."""
        src = _read('ui.js')
        assert 'SpeechSynthesisUtterance' in src, \
            "speakMessage must create SpeechSynthesisUtterance"
        assert 'speechSynthesis.speak' in src, \
            "speakMessage must call speechSynthesis.speak"


class TestTtsSpeakerButton:
    """Speaker button is rendered on assistant messages."""

    def test_tts_button_rendered(self):
        """ttsBtn must be generated for non-user messages."""
        src = _read('ui.js')
        assert 'msg-tts-btn' in src, \
            "TTS button class not found in ui.js"

    def test_tts_button_not_on_user_messages(self):
        """ttsBtn must only be added for non-user (assistant) messages."""
        src = _read('ui.js')
        # Find the ttsBtn definition — it should have !isUser guard
        tts_line = [l for l in src.splitlines() if 'msg-tts-btn' in l][0]
        assert '!isUser' in tts_line or 'isUser' in tts_line, \
            "TTS button should have user-check guard"

    def test_tts_button_in_footer(self):
        """ttsBtn must be included in the msg-actions span."""
        src = _read('ui.js')
        # The footHtml line should include ttsBtn
        foot_lines = [l for l in src.splitlines() if 'footHtml' in l and 'msg-actions' in l]
        assert any('ttsBtn' in l for l in foot_lines), \
            "ttsBtn not included in footHtml msg-actions"

    def test_tts_button_uses_volume_icon(self):
        """Speaker button should use volume-2 icon."""
        src = _read('ui.js')
        tts_line = [l for l in src.splitlines() if 'msg-tts-btn' in l][0]
        assert 'volume-2' in tts_line, \
            "TTS button should use volume-2 icon"


class TestTtsSettings:
    """TTS settings controls exist in the HTML and are wired in panels.js."""

    def test_tts_enabled_checkbox(self):
        src = _read('index.html')
        assert 'settingsTtsEnabled' in src, \
            "TTS enabled checkbox not found in index.html"

    def test_tts_auto_read_checkbox(self):
        src = _read('index.html')
        assert 'settingsTtsAutoRead' in src, \
            "TTS auto-read checkbox not found in index.html"

    def test_tts_voice_selector(self):
        src = _read('index.html')
        assert 'settingsTtsVoice' in src, \
            "TTS voice selector not found in index.html"

    def test_tts_rate_slider(self):
        src = _read('index.html')
        assert 'settingsTtsRate' in src, \
            "TTS rate slider not found in index.html"

    def test_tts_pitch_slider(self):
        src = _read('index.html')
        assert 'settingsTtsPitch' in src, \
            "TTS pitch slider not found in index.html"

    def test_tts_settings_wired_in_panels(self):
        """TTS settings must be initialized in loadSettingsPanel."""
        src = _read('panels.js')
        assert 'settingsTtsEnabled' in src, \
            "TTS enabled setting not wired in panels.js"
        assert '_applyTtsEnabled' in src, \
            "_applyTtsEnabled not called in panels.js"

    def test_apply_tts_enabled_function(self):
        """_applyTtsEnabled must toggle msg-tts-btn display."""
        src = _read('panels.js')
        assert 'function _applyTtsEnabled(' in src, \
            "_applyTtsEnabled function not found in panels.js"


class TestTtsI18n:
    """TTS i18n keys exist in the English locale."""

    def test_tts_listen_key(self):
        src = _read('i18n.js')
        assert "tts_listen:" in src, \
            "tts_listen key not found in i18n.js"

    def test_tts_not_supported_key(self):
        src = _read('i18n.js')
        assert "tts_not_supported:" in src, \
            "tts_not_supported key not found in i18n.js"

    def test_tts_settings_keys(self):
        src = _read('i18n.js')
        for key in ['settings_label_tts', 'settings_label_tts_auto_read',
                     'settings_label_tts_voice', 'settings_label_tts_rate',
                     'settings_label_tts_pitch']:
            assert f"{key}:" in src, f"{key} not found in i18n.js"


class TestTtsAutoRead:
    """Auto-read is triggered after SSE done event."""

    def test_auto_read_called_in_messages(self):
        src = _read('messages.js')
        assert 'autoReadLastAssistant' in src, \
            "autoReadLastAssistant not called in messages.js"

    def test_tts_pause_on_composer_focus(self):
        """Speech should pause when user focuses the composer."""
        src = _read('messages.js')
        assert 'speechSynthesis.pause' in src, \
            "speechSynthesis.pause not called in messages.js"
        assert 'speechSynthesis.resume' in src, \
            "speechSynthesis.resume not called in messages.js"


class TestTtsChatterboxVoice:
    """Selectable Chatterbox voice plumbing: client -> /api/tts -> Chatterbox.

    The /api/tts proxy lives as JS embedded in api/routes.py plus the Python
    handler _handle_tts_proxy; the client helpers live in the same embedded JS.
    """

    @staticmethod
    def _routes():
        path = os.path.join(os.path.dirname(__file__), '..', 'api', 'routes.py')
        return open(path, encoding='utf-8').read()

    def test_proxy_reads_voice_from_body(self):
        """_handle_tts_proxy must take voice from the request body, not hardcode alloy."""
        src = self._routes()
        assert 'body.get("voice")' in src, \
            "TTS proxy must read 'voice' from the request body"

    def test_proxy_has_env_default_voice(self):
        """Voice default must be env-configurable (VOICE_TOOLS_TTS_VOICE)."""
        src = self._routes()
        assert 'VOICE_TOOLS_TTS_VOICE' in src, \
            "TTS proxy must support a VOICE_TOOLS_TTS_VOICE env default"

    def test_proxy_sanitizes_voice(self):
        """Voice value must be charset-sanitized before being forwarded."""
        src = self._routes()
        assert 're.fullmatch' in src and 'A-Za-z0-9' in src, \
            "TTS proxy must sanitize the voice value against an allowlist charset"

    def test_proxy_no_longer_hardcodes_alloy_in_payload(self):
        """The synthesized payload must use the resolved voice variable, not a literal."""
        src = self._routes()
        # The payload line should reference the `voice` variable, not "voice": "alloy".
        assert re.search(r'"voice":\s*voice', src), \
            "TTS proxy payload must send the resolved `voice` variable"

    def test_client_voice_helper_exists(self):
        """A _hermesTTSVoice() helper must resolve the selected Chatterbox voice."""
        src = self._routes()
        assert 'window._hermesTTSVoice' in src, \
            "_hermesTTSVoice helper missing from embedded TTS JS"

    def test_client_voice_uses_distinct_key(self):
        """Chatterbox voice must use its own localStorage key, not the browser-voice key.

        'hermes-tts-voice' holds a browser SpeechSynthesis voice name (native
        fallback). Sending that to Chatterbox is meaningless, so the server-TTS
        voice must live under a separate key.
        """
        src = self._routes()
        assert 'hermes-tts-chatterbox-voice' in src, \
            "Chatterbox voice must use the dedicated 'hermes-tts-chatterbox-voice' key"

    def test_client_synth_passes_voice(self):
        """_synth must forward opts.voice in the /api/tts request body."""
        src = self._routes()
        assert 'reqBody.voice' in src, \
            "_synth must include the selected voice in the /api/tts body"


class TestTtsBoot:
    """TTS enabled state is applied on page load."""

    def test_apply_tts_on_boot(self):
        src = _read('boot.js')
        assert '_applyTtsEnabled' in src, \
            "_applyTtsEnabled not called in boot.js"


class TestTtsStyles:
    """TTS CSS styles exist."""

    def test_tts_button_hidden_default(self):
        src = _read('style.css')
        assert '.msg-tts-btn' in src, \
            ".msg-tts-btn CSS class not found in style.css"

    def test_tts_pulse_animation(self):
        src = _read('style.css')
        assert 'tts-pulse' in src, \
            "tts-pulse animation not found in style.css"


class TestIssue1409TtsToggleBodyClass:
    """Regression: #1409 — TTS toggle had no effect because of CSS specificity collision.

    Original bug: ``_applyTtsEnabled`` set ``btn.style.display=enabled?'':'none'``.
    The empty-string branch removes the inline override, after which the
    ``.msg-tts-btn { display:none; }`` rule from style.css applies — so both
    "enabled" and "disabled" states left the button hidden.

    Fix: toggle a body-level class (``body.tts-enabled``) and gate the speaker
    icon on a compound selector ``body.tts-enabled .msg-tts-btn``. This bypasses
    the inline-style cascade collision and survives ``renderMd()`` re-renders.
    """

    def test_apply_tts_enabled_uses_body_class(self):
        """_applyTtsEnabled must toggle the document body's `tts-enabled` class."""
        src = _read('panels.js')
        # The new shape: toggle body class instead of writing inline display
        assert "document.body.classList.toggle('tts-enabled'" in src, (
            "_applyTtsEnabled must toggle the body.tts-enabled class — see #1409. "
            "Reverting to inline `style.display` will silently break the toggle "
            "again because of the .msg-action-btn / .msg-tts-btn cascade."
        )

    def test_apply_tts_enabled_does_not_use_inline_display(self):
        """_applyTtsEnabled must NOT set inline `style.display` on .msg-tts-btn."""
        src = _read('panels.js')
        # Find the function body and check it doesn't set inline display
        # on individual buttons (the broken pattern).
        m = re.search(
            r'function _applyTtsEnabled\([^)]*\)\s*\{(?P<body>[^}]*)\}',
            src,
        )
        assert m, "_applyTtsEnabled function body not found in panels.js"
        body = m.group('body')
        assert '.style.display' not in body, (
            "_applyTtsEnabled body must not set inline style.display — that's "
            "the #1409 bug. Use body.classList.toggle('tts-enabled') instead."
        )

    def test_body_class_selector_in_css(self):
        """style.css must show .msg-tts-btn only when body.tts-enabled is set."""
        src = _read('style.css')
        assert 'body.tts-enabled .msg-tts-btn' in src, (
            "Missing `body.tts-enabled .msg-tts-btn` selector in style.css — "
            "without this rule the body class has no visual effect (#1409)."
        )
        # The default-hidden rule must still be present (so no body class = no icon).
        assert '.msg-tts-btn{display:none;}' in src or \
               re.search(r'\.msg-tts-btn\s*\{[^}]*display\s*:\s*none', src), (
            "Default `.msg-tts-btn{display:none;}` rule must remain so the "
            "icon is hidden by default (#1409)."
        )
