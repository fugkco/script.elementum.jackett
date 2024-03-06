from kodi_six import xbmcgui


class PDialog:
    default_heading = 'Elementum [COLOR FFFF6B00]Jackett[/COLOR]'

    def __init__(self, msg, heading=default_heading):
        self.heading = None
        self.start_pg = None
        self.curr_pg = None
        self.to_pg = None
        self.pd = xbmcgui.DialogProgressBG()
        self._init(msg, heading)

    def _init(self, msg, heading):
        self.pd.create(heading, msg)
        self.heading = heading
        self.start_pg = 0
        self.curr_pg = 0
        self.to_pg = 100

    def reset(self, msg, heading=default_heading):
        self.pd.close()
        self._init(msg, heading)

    def callback(self, to_pg):
        self.start_pg = self.curr_pg
        self.to_pg = 100 if 0 > to_pg > 100 else to_pg
        return self.update_progress

    def update(self, percent=None, heading=default_heading, message=None):
        self.curr_pg = percent if percent is not None else self.curr_pg
        self.pd.update(self.curr_pg, heading, message)

    def update_progress(self, curr_step=0, total_steps=100, heading: str = default_heading, message: str = None):
        self.curr_pg = int((self.start_pg + (self.to_pg - self.start_pg) * (curr_step / total_steps)) // 1)
        self.pd.update(self.curr_pg, heading, message)

    def close(self):
        self.pd.close()

    def __del__(self):
        del self.pd
