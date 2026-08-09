import tkinter as tk, numpy as np, librosa

class Timeline(tk.Canvas):
    lanes=["Kick","Snare","Closed Hat","Open Hat","Clap","Roll","Snare Roll","FX"]
    def __init__(self,parent,select_cb=None,seek_cb=None,**kw):
        super().__init__(parent,bg="#0b0d10",highlightthickness=0,**kw)
        self.select_cb=select_cb; self.seek_cb=seek_cb
        self.y=None; self.sr=44100; self.duration=1; self.events=[]
        self.zoom=1; self.offset=0; self.playhead=0; self.selected=None
        self.lane_h=78; self.ruler_h=28
        self.bind("<Button-1>",self.click); self.bind("<MouseWheel>",self.wheel)
        self.bind("<B1-Motion>",self.drag)
    def set_audio(self,y,sr,events):
        self.y=y; self.sr=sr; self.duration=max(.01,len(y)/sr); self.events=events
        self.offset=0; self.zoom=max(1,self.zoom); self.redraw()
    def time_to_x(self,t):
        w=max(1,self.winfo_width()-220); return 220+(t/self.duration)*w*self.zoom-self.offset
    def x_to_time(self,x):
        w=max(1,self.winfo_width()-220); return max(0,min(self.duration,((x-220+self.offset)/(w*self.zoom))*self.duration))
    def lane_y(self,i): return self.ruler_h+i*self.lane_h
    def click(self,e):
        t=self.x_to_time(e.x)
        self.playhead=t
        hit=None
        for ev in self.events:
            if abs(self.time_to_x(ev["time"])-e.x)<8 and self.lane_y(self.lanes.index(ev["type"]))<e.y<self.lane_y(self.lanes.index(ev["type"])+1):
                hit=ev;break
        self.selected=hit
        if self.select_cb:self.select_cb(hit)
        if self.seek_cb:self.seek_cb(t)
        self.redraw()
    def drag(self,e):
        self.playhead=self.x_to_time(e.x); 
        if self.seek_cb:self.seek_cb(self.playhead)
        self.redraw()
    def wheel(self,e):
        factor=1.18 if e.delta>0 else 1/1.18
        anchor=self.x_to_time(e.x)
        self.zoom=max(1,min(20,self.zoom*factor))
        w=max(1,self.winfo_width()-220)
        self.offset=max(0,anchor/self.duration*w*self.zoom-(e.x-220))
        self.redraw()
    def redraw(self):
        self.delete("all")
        W=max(800,self.winfo_width()); H=self.ruler_h+len(self.lanes)*self.lane_h
        self.configure(scrollregion=(0,0,W*self.zoom,H))
        # ruler
        self.create_rectangle(0,0,W,H,fill="#0b0d10",outline="")
        step=1
        if self.duration>60:step=10
        elif self.duration>20:step=5
        elif self.duration>8:step=2
        t=0
        while t<=self.duration:
            x=self.time_to_x(t); self.create_line(x,0,x,H,fill="#20262e")
            self.create_text(x+3,12,text=f"{t:.1f}s",anchor="w",fill="#7d8793",font=("Segoe UI",8))
            t+=step
        # lanes and waveform
        colors=["#ff5b6e","#5b9cff","#e6d44b","#f2a23a","#b978ff","#9b7cff","#d84cff","#4bd4d4"]
        if self.y is not None:
            n=2400
            idx=np.linspace(0,len(self.y)-1,min(n,len(self.y))).astype(int)
            yy=self.y[idx]
            tt=np.linspace(0,self.duration,len(idx))
            for i,lane in enumerate(self.lanes):
                y0=self.lane_y(i)
                self.create_rectangle(0,y0,W,y0+self.lane_h,fill="#101419",outline="#171d24")
                # faint source waveform in every lane, visually useful for editing
                amp=(self.lane_h*.30)
                pts=[]
                for q in range(len(tt)):
                    x=self.time_to_x(float(tt[q]))
                    if -2<x<W+2: pts += [x,y0+self.lane_h/2-yy[q]*amp]
                if len(pts)>=4:self.create_line(*pts,fill="#263441",width=1)
                self.create_text(8,y0+15,text=lane,anchor="w",fill=colors[i],font=("Segoe UI",9,"bold"))
        for i,lane in enumerate(self.lanes):
            y0=self.lane_y(i)
            for ev in self.events:
                if ev["type"]!=lane:continue
                x=self.time_to_x(ev["time"])
                c=colors[i]; r=5 if ev is self.selected else 4
                self.create_line(x,y0+26,x,y0+self.lane_h-8,fill=c,width=2)
                self.create_oval(x-r,y0+31-r,x+r,y0+31+r,fill=c,outline="")
                if ev is self.selected:self.create_text(x+7,y0+18,text=f'{ev["time"]:.3f}s',anchor="w",fill="#fff",font=("Segoe UI",8))
        px=self.time_to_x(self.playhead)
        self.create_line(px,0,px,H,fill="#ffffff",width=2)
        self.create_polygon(px-5,0,px+5,0,px,7,fill="#fff",outline="")
