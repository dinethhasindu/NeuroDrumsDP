import tkinter as tk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle

LANES=["Kick","Snare","Closed Hat","Open Hat","Clap","Roll","Snare Roll","FX"]

class WaveformViewer:
    def __init__(self,parent,on_event_click=None,on_seek=None):
        self.parent=parent; self.on_event_click=on_event_click; self.on_seek=on_seek
        self.fig=Figure(figsize=(12,7),dpi=95,facecolor="#0b0c0f")
        self.canvas=FigureCanvasTkAgg(self.fig,master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)
        self.canvas.mpl_connect("button_press_event",self._click)
        self.canvas.mpl_connect("scroll_event",self._scroll)
        self.y=None; self.sr=44100; self.events=[]; self.duration=1
        self.zoom=1.0; self.center=0.5; self.playhead=0
        self.selected=None

    def set_audio(self,y,sr,events):
        self.y=np.asarray(y); self.sr=sr; self.events=events or []
        self.duration=len(y)/sr; self.center=self.duration/2; self.zoom=1
        self.draw()

    def draw(self):
        self.fig.clear()
        gs=self.fig.add_gridspec(len(LANES)+1,1,height_ratios=[.6]+[1]*len(LANES),hspace=.08)
        ax0=self.fig.add_subplot(gs[0,0]); ax0.set_facecolor("#0b0c0f")
        ax0.set_yticks([]); ax0.set_ylabel("TIME",color="#7dd3fc",fontsize=8)
        self._wave(ax0,self.y,alpha=.35)
        self._setup_ax(ax0)
        axes=[ax0]
        for lane_i,lane in enumerate(LANES):
            ax=self.fig.add_subplot(gs[lane_i+1,0],sharex=ax0); ax.set_facecolor("#111318")
            self._setup_ax(ax); ax.text(.002,.5,lane,transform=ax.transAxes,va="center",
                                        fontsize=8,fontweight="bold",color="#9ca3af")
            evs=[e for e in self.events if e["type"]==lane]
            for j,e in enumerate(evs):
                t=e["time"]; c="#60a5fa"
                if lane=="Kick": c="#fb7185"
                elif lane=="Snare" or lane=="Snare Roll": c="#a78bfa"
                elif "Hat" in lane: c="#fbbf24"
                elif lane=="Clap": c="#34d399"
                elif lane=="FX": c="#22d3ee"
                ax.axvline(t,color=c,alpha=.95,lw=1.2)
                ax.scatter([t],[0],s=16,color=c,zorder=5)
                # Draw a tiny waveform snippet for this event inside its lane.
                if self.y is not None:
                    a=max(0,int((t-0.045)*self.sr))
                    b=min(len(self.y),int((t+0.12)*self.sr))
                    if b>a+8:
                        yy=self.y[a:b]
                        # downsample each event to keep the editor responsive
                        n=min(90,len(yy))
                        ix=np.linspace(0,len(yy)-1,n).astype(int)
                        tt=(np.arange(n)/max(1,n-1))*0.165 + (t-0.045)
                        scale=max(np.max(np.abs(yy[ix])),1e-5)
                        ax.plot(tt,0.62*yy[ix]/scale,color=c,alpha=.62,lw=.55)
            axes.append(ax)
        x0,x1=self.view_window()
        for ax in axes: ax.set_xlim(x0,x1)
        # top time ticks
        axes[0].set_xticks(np.linspace(x0,x1,9))
        axes[0].set_xticklabels([f"{x:.1f}s" for x in np.linspace(x0,x1,9)],color="#64748b",fontsize=7)
        for ax in axes[1:]: ax.tick_params(axis="x",bottom=False,labelbottom=False)
        for ax in axes: ax.axvline(self.playhead,color="#f8fafc",lw=1.3,alpha=.95)
        self.canvas.draw_idle()

    def _wave(self,ax,y,alpha=.5):
        if y is None: return
        n=4000
        idx=np.linspace(0,len(y)-1,min(n,len(y))).astype(int)
        t=idx/self.sr
        ax.plot(t,y[idx],color="#38bdf8",alpha=alpha,lw=.55)

    def _setup_ax(self,ax):
        ax.set_ylim(-1,1); ax.set_yticks([])
        for s in ax.spines.values(): s.set_visible(False)
        ax.grid(axis="x",color="#20242c",lw=.5,alpha=.7)

    def view_window(self):
        width=self.duration/self.zoom
        width=max(.5,min(self.duration,width))
        x0=max(0,self.center-width/2); x1=min(self.duration,x0+width)
        x0=max(0,x1-width)
        return x0,x1

    def set_playhead(self,t):
        self.playhead=float(np.clip(t,0,self.duration)); self.draw()

    def _scroll(self,e):
        if e.xdata is None: return
        factor=.8 if e.button=="up" else 1.25
        old=self.view_window(); oldw=old[1]-old[0]
        neww=max(.5,min(self.duration,oldw*factor))
        self.zoom=self.duration/neww
        # keep mouse position fixed
        rel=(e.xdata-old[0])/max(oldw,1e-9)
        self.center=e.xdata+(0.5-rel)*neww
        self.center=np.clip(self.center,neww/2,max(neww/2,self.duration-neww/2))
        self.draw()

    def _click(self,e):
        if e.xdata is None: return
        if e.button==1:
            # seek
            if e.inaxes and self.on_seek:
                self.on_seek(float(np.clip(e.xdata,0,self.duration)))
            # select closest event in clicked lane
            if e.inaxes and e.inaxes.get_ylabel():
                pass
            closest=min(self.events,key=lambda x:abs(x["time"]-e.xdata)) if self.events else None
            if closest and abs(closest["time"]-e.xdata)<0.08 and self.on_event_click:
                self.on_event_click(closest)
