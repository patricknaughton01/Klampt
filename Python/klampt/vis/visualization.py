"""Klamp't world visualization routines.  See demos/vistemplate.py for an
example of how to run this module.

WHAT DO WE WANT:
- Everything visualization-related is goverend by the klampt.vis module.
- Simple startup: create a GLProgramInterface and run a GUI using a single
  line of code, or simply add items to the visualization and run the GUI.
- Parallelize GUI and script code: launch a GUI, modify items of a world /
  simulation through a script, close the GUI or wait for the user to close
  the window.
- Window customizability with Qt.  Add the GLProgramInterface to an existing window
  and launch it.
- Add/remove/animate/configure all items in visualization using one-liners
- Multiple windows, shown either sequentially or simultaneously

CHALLENGES:
- Desire for window customizability breaks abstraction over GLUT / Qt.  Solution:
  None.  Possibly demand Qt?  Compatibility vs. complexity tradeoff.
- Parallel GUI / script execution has locking issues.  Solution: put 
  locks around everything visualization related, and require user to call
  vis.lock() and vis.unlock().
- Multiple windows has the problem of GL display lists not passing from context
  to context. 
  Solutions:
  - Print warnings if the same world is passed to multiple simultaneous windows.
  - When windows are closed they become "dormant" and can wake up again:
    - Qt: simply hide the GL widget but keep it around to be passed to other windows.
    - GLUT: hide the window rather than closing it. 
- GLUT doesn't allow modal dialog boxes. 
  Solution: disable signals to non-modal windows?

NEW PROBLEM: 
- Qt seems to save display lists, so that each gl window has the same GL context?
  Cannot reuse widgets for new windows.
- GLUT does not, so things disappear when you create a new window.

Instructions:

- To add things to the default visualization:
  Call the VisualizationPlugin aliases (add, animate, setColor, etc)

- To show the visualization and quit when the user closes the window:
  run()

- To show the visualization and return when the user closes the window:
  dialog()
  ... do stuff afterwards ... 
  kill()

- To show the visualization and be able to run a script alongside it
  until the user closes the window:
  show()
  while shown():
      lock()
      ... do stuff ...
      [to exit the loop call show(False)]
      unlock()
      time.sleep(dt)
  ... do stuff afterwards ...
  kill()

- To run a window with a custom plugin (GLProgramInterface) and terminate on
  closure: 
  run(plugin)

- To show a dialog or parallel window
  setPlugin(plugin)
  ... then call  
  dialog()
  ... or
  show()
  ... do stuff afterwards ... 
  kill()

- To add a GLProgramInterface that just customizes a few things on top of
  the default visualization:
  pushPlugin(plugin)
  dialog()
  popPlugin()

- To run plugins side-by-side in the same window:
  setPlugin(plugin1)
  addPlugin(plugin2)
  dialog()
  ... or
  show()
  ... do stuff afterwards ... 
  kill()

- To run a custom dialog in a QtWindow
  setPlugin([desired plugin or None for visualization])
  setParent(qt_window)
  dialog()
  ... or 
  show()
  ... do stuff afterwards ... 
  kill()

- To launch a second window after the first is closed: just call whatever you
  want again. Note: if show was previously called with a plugin and you wish to
  revert to the default visualization, you should call setPlugin(None) first to 
  restore the default.

- To create a separate window with a given plugin:
  w1 = createWindow()  #w1=0
  show()
  w2 = createWindow()  #w2=1
  setPlugin(plugin)
  dialog()
  #to restore commands to the original window
  setWindow(w1)
  while shown():
      ...
  kill()

Due to weird OpenGL behavior when opening/closing windows, you should only
run visualizations using the methods in this module.

Note: when changing the data shown by the window (e.g., modifying the
configurations of robots in a WorldModel) you must call lock() before
accessing the data and then call unlock() afterwards.

The main interface is as follows:

def createWindow(title=None): creates a new visualization window and returns an
    integer identifier.
def setWindow(id): sets the active window for all subsequent calls.  ID 0 is
    the default visualization window.
def getWindow(): gets the active window ID.
def setWindowTitle(title): sets the title of the visualization window.
def getWindowTitle(): returns the title of the visualization window
def setPlugin(plugin=None): sets the current plugin
def run([plugin]): pops up a dialog and then kills the program afterwards.
def kill(): kills all previously launched visualizations.  Afterwards, you may not
    be able to start new windows. Call this to cleanly quit.
def dialog(): pops up a dialog box (does not return to calling
    thread until closed).
def show(hidden=False): shows/hides a visualization window run in parallel with the calling script.
def spin(duration): shows the visualization window for the desired amount
    of time before returning, or until the user closes the window.
def shown(): returns true if the window is shown.
def lock(): locks the visualization world for editing.  The visualization will
    be paused until unlock() is called.
def unlock(): unlocks the visualization world.  Must only be called once
    after every lock().
def customRun(func): internal use... need to deprecate this


The following VisualizationPlugin methods are also added to the klampt.vis namespace
and operate on the default plugin:

def add(name,item,keepAppearance=False): adds an item to the visualization.
    name is a unique identifier.  If an item with the same name already exists,
    it will no longer be shown.  If keepAppearance=True, then the prior item's
    appearance will be kept, if a prior item exists.
def clear(): clears the visualization world.
def dirty(item_name='all'): marks the given item as dirty and recreates the
    OpenGL display lists.
def remove(name): removes an item from the visualization.
def setItemConfig(name,vector): sets the configuration of a named item.
def getItemConfig(name): returns the configuration of a named item.
def hide(name,hidden=True): hides/unhides an item.  The item is not removed,
    it just becomes invisible.
def hideLabel(name,hidden=True): hides/unhides an item's text label.
def animate(name,animation,speed=1.0): Sends an animation to the object.
    May be a Trajectory or a list of configurations.  Works with points,
    so3 elements, se3 elements, rigid objects, or robots.
def setAppearance(name,appearance): changes the Appearance of an item.
def revertAppearance(name): restores the Appearance of an item
def setAttribute(name,attribute,value): sets an attribute of the appearance
    of an item.  Typical attributes are color, size, length, width...
    TODO: document all accepted attributes.
def setColor(name,r,g,b,a=1.0): changes the color of an item.
def setPlugin(plugin): plugin must be an instance of a GLPluginBase. 
    This plugin will now capture input from the visualization and can override
    any of the default behavior of the visualizer.
def pauseAnimation(paused=True): Turns on/off animation.
def stepAnimation(amount): Moves forward the animation time by the given amount
    in seconds
def animationTime(newtime=None): Gets/sets the current animation time
    If newtime == None (default), this gets the animation time.
    If newtime != None, this sets a new animation time.
"""


from OpenGL.GL import *
from threading import Thread,Lock
from ..robotsim import *
from ..math import vectorops,so3,se3
import gldraw
from glinit import *
from glinit import _GLBackend,_PyQtAvailable,_GLUTAvailable
from glinterface import GLProgramInterface
from glprogram import GLPluginProgram
import glcommon
import time
import signal
from ..model import types
from ..model import coordinates
from ..model.trajectory import *
from ..model.contact import ContactPoint,Hold

_globalLock = Lock()
_vis = None
_frontend = GLPluginProgram()
_window_title = "Klamp't visualizer"
_windows = []
_current_window = None

class WindowInfo:
    """Mode can be hidden, shown, or dialog"""
    def __init__(self,name,frontend,vis,window=None):
        self.name = name
        self.frontend = frontend
        self.vis = vis
        self.window = window
        self.mode = 'shown'
        self.guidata = None

def createWindow(name):
    """Creates a new window."""
    global _globalLock,_frontend,_vis,_window_title,_windows,_current_window
    _globalLock.lock()
    if len(_windows) == 0:
        #save the defaults
        _windows.append(WindowInfo(_window_title,_frontend,_vis))
    else:
        #make a new window
        _window_title = name
        _frontend = GLPluginProgram()
        _vis = VisualizationPlugin()
        _windows.append(WindowInfo(_window_title,_frontend,_vis))
    id = len(_windows)-1
    _current_window = id
    _globalLock.unlock()
    return id

def setWindow(id):
    """Sets currently active window."""
    global _globalLock,_frontend,_vis,_window_title,_windows,_current_window
    assert id >= 0 and id < len(_windows)
    if id == _current_window:
        return
    _globalLock.lock()
    _window_title,_frontend,_vis = _windows[id].name,_windows[id].frontend,_windows[id].vis
    _current_window = id
    _globalLock.unlock()

def getWindow():
    """Retrieves ID of currently active window or -1 if no window is active"""
    global _current_window
    if _current_window == None: return -1
    return _current_window

def setPlugin(plugin):
    """Lets the user capture input via a glinterface.GLProgramInterface class.
    Set plugin to None to disable plugins and return to the standard visualization"""
    global _frontend
    if not isinstance(_frontend,GLPluginProgram):
        _frontend = GLPluginProgram()
    if plugin == None:
        global _vis
        if _vis==None:
            raise RuntimeError("Visualization disabled")
        _frontend.setPlugin(_vis)
    else:
        _frontend.setPlugin(plugin)
    _onFrontendChange()

def pushPlugin(plugin):
    """Adds a new glinterface.GLProgramInterface plugin on top of the old one."""
    global _frontend
    assert isinstance(_frontend,GLPluginProgram),"Can't push a plugin after addPlugin"
    if len(_frontend.plugins) == 0:
        global _vis
        if _vis==None:
            raise RuntimeError("Visualization disabled")
        _frontend.setPlugin(_vis)
    _frontend.pushPlugin(plugin)
    _onFrontendChange()

def popPlugin():
    global _frontend
    _frontend.popPlugin(plugin)
    _onFrontendChange()

def addPlugin(plugin):
    global _frontend
    #create a multi-view widget
    if isinstance(_frontend,GLMultiProgramInterface):
        _frontend.addPlugin(plugin)
    else:
        if len(_frontend.plugins) == 0:
            setPlugin(None)
        multiProgram = GLMultiProgramInterface()
        multiProgram.window = None
        multiProgram.addPlugin(_frontend)
        multiProgram.addPlugin(plugin)
        _frontend = multiProgram
    _onFrontendChange()


def run(plugin=None):
    """A blocking call to start a single window.  If plugin == None,
    the default visualization is used.  Otherwise, the plugin is used."""
    _globalLock.acquire()
    setPlugin(plugin)
    _globalLock.release()
    dialog()
    kill()

def dialog():
    _dialog()

def setWindowTitle(title):
    global _window_title
    _window_title = title

def getWindowTitle():
    global _window_title
    return _window_title

def kill():
    global _vis,_globalLock
    if _vis==None:
        print "Visualization disabled"
        return
    _kill()

def show(hidden=False):
    _globalLock.acquire()
    if hidden:
        _hide()
    else:
        _show()
    _globalLock.release()

def spin(duration):
    show()
    t = 0
    while t < duration:
        if not shown(): break
        time.sleep(min(0.1,duration-t))
        t += 0.1
    return

def lock():
    global _globalLock
    _globalLock.acquire()

def unlock():
    global _globalLock
    _globalLock.release()

def shown():
    global _globalLock,_thread_running,_current_window
    _globalLock.acquire()
    res = (_thread_running and _current_window != None and _windows[_current_window].mode in ['shown','dialog'])
    _globalLock.release()
    return res



######### CONVENIENCE ALIASES FOR VisualizationPlugin methods ###########
def clear():
    global _vis
    if _vis==None:
        return
    _vis.clear()

def add(name,item,keepAppearance=False):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return
    _vis.add(name,item,keepAppearance)

def dirty(item_name='all'):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return
    _vis.dirty(item_name)

def animate(name,animation,speed=1.0):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return
    _vis.animate(name,animation,speed)

def pauseAnimation(paused=True):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return
    _vis.pauseAnimation(paused)

def stepAnimation(amount):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return
    _vis.stepAnimation(amount)

def animationTime(newtime=None):
    global _vis
    if _vis==None:
        print "Visualization disabled"
        return 0
    return _vis.animationTime(newtime)

def remove(name):
    global _vis
    if _vis==None:
        return
    return _vis.remove(name)

def getItemConfig(name):
    global _vis
    if _vis==None:
        return None
    return _vis.getItemConfig(name)

def setItemConfig(name,value):
    global _vis
    if _vis==None:
        return
    return _vis.setItemConfig(name,value)

def hideLabel(name,hidden=True):
    global _vis
    if _vis==None:
        return
    return _vis.hideLabel(name,hidden)

def hide(name,hidden=True):
    global _vis
    if _vis==None:
        return
    _vis.hide(name,hidden)

def setAppearance(name,appearance):
    global _vis
    if _vis==None:
        return
    _vis.setAppearance(name,appearance)

def setAttribute(name,attr,value):
    global _vis
    if _vis==None:
        return
    _vis.setAttribute(name,attr,value)

def revertAppearance(name):
    global _vis
    if _vis==None:
        return
    _vis.revertAppearance(name)

def setColor(name,r,g,b,a=1.0):
    global _vis
    if _vis==None:
        return
    _vis.setColor(name,r,g,b,a)




class CachedGLObject:
    """An object whose drawing is accelerated by means of a display list.
    The draw function may draw the object in the local frame, and the
    object may be transformed without having to recompile the display list.
    """
    def __init__(self):
        self.name = ""
        #OpenGL display list
        self.glDisplayList = None
        #marker for recursive calls
        self.makingDisplayList = False
        #parameters for display lists
        self.displayListParameters = None
        #dirty bit to indicate whether the display list should be recompiled
        self.changed = False

    def destroy(self):
        """Must be called to free up resources used by this object"""
        if self.glDisplayList != None:
            glDeleteLists(self.glDisplayList,1)
            self.glDisplayList = None

    def markChanged(self):
        """Marked by an outside source to indicate the object has changed and
        should be redrawn."""
        self.changed = True
    
    def draw(self,renderFunction,transform=None,parameters=None):
        """Given the function that actually makes OpenGL calls, this
        will draw the object.

        If parameters is given, the object's local appearance is assumed
        to be defined deterministically from these parameters.  The display
        list will be redrawn if the parameters change.
        """
        if self.makingDisplayList:
            renderFunction()
            return
        if self.glDisplayList == None or self.changed or parameters != self.displayListParameters:
            self.displayListParameters = parameters
            self.changed = False
            if self.glDisplayList == None:
                #print "Generating new display list",self.name
                self.glDisplayList = glGenLists(1)
            #print "Compiling display list",self.name
            if transform:
                glPushMatrix()
                glMultMatrixf(sum(zip(*se3.homogeneous(transform)),()))
            
            glNewList(self.glDisplayList,GL_COMPILE_AND_EXECUTE)
            self.makingDisplayList = True
            renderFunction()
            self.makingDisplayList = False
            glEndList()

            if transform:
                glPopMatrix()
        else:
            if transform:
                glPushMatrix()
                glMultMatrixf(sum(zip(*se3.homogeneous(transform)),()))
            glCallList(self.glDisplayList)
            if transform:
                glPopMatrix()

class VisAppearance:
    def __init__(self,item,name = None):
        self.name = name
        self.hidden = False
        self.useDefaultAppearance = True
        self.customAppearance = None
        #For group items, this allows you to customize appearance of sub-items
        self.subAppearances = {}
        self.animation = None
        self.animationStartTime = 0
        self.animationSpeed = 1.0
        self.attributes = {}
        #used for Qt text rendering
        self.widget = None
        #cached drawing
        self.displayCache = [CachedGLObject()]
        self.displayCache[0].name = name
        #temporary configuration of the item
        self.drawConfig = None
        self.setItem(item)
    def setItem(self,item):
        self.item = item
        self.subAppearances = {}
        #Parse out sub-items which can have their own appearance changed
        if isinstance(item,coordinates.Group):
            for n,f in item.frames.iteritems():
                self.subAppearances[("Frame",n)] = VisAppearance(f,n)
            for n,p in item.points.iteritems():
                self.subAppearances[("Point",n)] = VisAppearance(p,n)
            for n,d in item.directions.iteritems():
                self.subAppearances[("Direction",n)] = VisAppearance(d,n)
            for n,g in item.subgroups.iteritems():
                self.subAppearances[("Subgroup",n)] = VisAppearance(g,n)
        if isinstance(item,Hold):
            if item.ikConstraint is not None:
                self.subAppearances["ikConstraint"] = VisAppearance(item.ikConstraint,"ik")
            for n,c in enumerate(item.contacts):
                self.subAppearances[("contact",n)] = VisAppearance(c,n)
        for (k,a) in self.subAppearances.iteritems():
            a.attributes = self.attributes
            
    def markChanged(self):
        for c in self.displayCache:
            c.markChanged()
        for (k,a) in self.subAppearances.iteritems():
            a.markChanged()

    def destroy(self):
        for c in self.displayCache:
            c.destroy()
        for (k,a) in self.subAppearances.iteritems():
            a.destroy()
        self.subAppearances = {}
        
    def drawText(self,text,point):
        """Draws the given text at the given point"""
        if self.attributes.get("text_hidden",False): return
        self.widget.addLabel(text,point,[0,0,0])

    def update(self,t):
        """Updates the configuration, if it's being animated"""
        if not self.animation:
            self.drawConfig = None
        else:
            u = self.animationSpeed*(t-self.animationStartTime)
            q = self.animation.eval(u,'loop')
            self.drawConfig = q
        for n,app in self.subAppearances.iteritems():
            app.update(t)

    def swapDrawConfig(self):
        """Given self.drawConfig!=None, swaps out the item's curren
        configuration  with self.drawConfig.  Used for animations"""
        if self.drawConfig: 
            try:
                newDrawConfig = config.getConfig(self.item)
                self.item = config.setConfig(self.item,self.drawConfig)
                self.drawConfig = newDrawConfig
            except Exception as e:
                print "Warning, exception thrown during animation update.  Probably have incorrect length of configuration"
                print e
                pass
        for n,app in self.subAppearances.iteritems():
            app.swapDrawConfig()        

    def clearDisplayLists(self):
        if isinstance(self.item,WorldModel):
            for r in range(self.item.numRobots()):
                for link in range(self.item.robot(r).numLinks()):
                    self.item.robot(r).link(link).appearance().refresh()
            for i in range(self.item.numRigidObjects()):
                self.item.rigidObject(i).appearance().refresh()
            for i in range(self.item.numTerrains()):
                self.item.terrain(i).appearance().refresh()
        elif hasattr(self.item,'appearance'):
            self.item.appearance().refresh()
        elif isinstance(self.item,RobotModel):
            for link in range(self.item.numLinks()):
                self.item.link(link).appearance().refresh()
        self.markChanged()

    def draw(self,world=None):
        """Draws the specified item in the specified world.  If name
        is given and text_hidden != False, then the name of the item is
        shown."""
        if self.hidden: return
       
        item = self.item
        name = self.name
        #set appearance
        if not self.useDefaultAppearance and hasattr(item,'appearance'):
            if not hasattr(self,'oldAppearance'):
                self.oldAppearance = item.appearance().clone()
            if self.customAppearance != None:
                print "Changing appearance of",name
                item.appearance().set(self.customAppearance)
            elif "color" in self.attributes:
                print "Changing color of",name
                item.appearance().setColor(*self.attributes["color"])

        if hasattr(item,'drawGL'):
            item.drawGL()
        elif len(self.subAppearances)!=0:
            for n,app in self.subAppearances.iteritems():
                app.widget = self.widget
                app.draw(world)
        elif isinstance(item,coordinates.Point):
            def drawRaw():
                glDisable(GL_DEPTH_TEST)
                glDisable(GL_LIGHTING)
                glEnable(GL_POINT_SMOOTH)
                glPointSize(self.attributes.get("size",5.0))
                glColor4f(*self.attributes.get("color",[0,0,0,1]))
                glBegin(GL_POINTS)
                glVertex3f(0,0,0)
                glEnd()
                glEnable(GL_DEPTH_TEST)
                #write name
            self.displayCache[0].draw(drawRaw,[so3.identity(),item.worldCoordinates()])
            if name != None:
                self.drawText(name,vectorops.add(item.worldCoordinates(),[0,0,-0.05]))
        elif isinstance(item,coordinates.Direction):
            def drawRaw():
                glDisable(GL_LIGHTING)
                glDisable(GL_DEPTH_TEST)
                L = self.attributes.get("length",0.15)
                source = [0,0,0]
                glColor4f(*self.attributes.get("color",[0,1,1,1]))
                glBegin(GL_LINES)
                glVertex3f(*source)
                glVertex3f(*vectorops.mul(item.localCoordinates(),L))
                glEnd()
                glEnable(GL_DEPTH_TEST)
                #write name
            self.displayCache[0].draw(drawRaw,item.frame().worldCoordinates(),parameters = item.localCoordinates())
            if name != None:
                self.drawText(name,vectorops.add(vectorops.add(item.frame().worldCoordinates()[1],item.worldCoordinates()),[0,0,-0.05]))
        elif isinstance(item,coordinates.Frame):
            t = item.worldCoordinates()
            if item.parent() != None:
                tp = item.parent().worldCoordinates()
            else:
                tp = se3.identity()
            tlocal = item.relativeCoordinates()
            def drawRaw():
                glDisable(GL_DEPTH_TEST)
                glDisable(GL_LIGHTING)
                glLineWidth(2.0)
                gldraw.xform_widget(tlocal,self.attributes.get("length",0.1),self.attributes.get("width",0.01))
                glLineWidth(1.0)
                #draw curve between frame and parent
                if item.parent() != None:
                    d = vectorops.norm(tlocal[1])
                    vlen = d*0.5
                    v1 = so3.apply(tlocal[0],[-vlen]*3)
                    v2 = [vlen]*3
                    #glEnable(GL_BLEND)
                    #glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
                    #glColor4f(1,1,0,0.5)
                    glColor3f(1,1,0)
                    gldraw.hermite_curve(tlocal[1],v1,[0,0,0],v2,0.03)
                    #glDisable(GL_BLEND)
                glEnable(GL_DEPTH_TEST)

            #For some reason, cached drawing is causing OpenGL problems
            #when the frame is rapidly changing
            #self.displayCache[0].draw(drawRaw,transform=tp, parameters = tlocal)
            glPushMatrix()
            glMultMatrixf(sum(zip(*se3.homogeneous(tp)),()))
            drawRaw()
            glPopMatrix()
            #write name
            if name != None:
                self.drawText(name,se3.apply(t,[-0.05]*3))
        elif isinstance(item,coordinates.Transform):
            #draw curve between frames
            t1 = item.source().worldCoordinates()
            if item.destination() != None:
                t2 = item.destination().worldCoordinates()
            else:
                t2 = se3.identity()
            d = vectorops.distance(t1[1],t2[1])
            vlen = d*0.5
            v1 = so3.apply(t1[0],[-vlen]*3)
            v2 = so3.apply(t2[0],[vlen]*3)
            def drawRaw():
                glDisable(GL_DEPTH_TEST)
                glDisable(GL_LIGHTING)
                glColor3f(1,1,1)
                gldraw.hermite_curve(t1[1],v1,t2[1],v2,0.03)
                glEnable(GL_DEPTH_TEST)
                #write name at curve
            self.displayCache[0].draw(drawRaw,transform=None,parameters = (t1,t2))
            if name != None:
                self.drawText(name,spline.hermite_eval(t1[1],v1,t2[1],v2,0.5))
        elif isinstance(item,coordinates.Group):
            pass
        elif isinstance(item,ContactPoint):
            def drawRaw():
                glDisable(GL_LIGHTING)
                glEnable(GL_POINT_SMOOTH)
                glPointSize(self.attributes.get("size",5.0))
                l = self.attributes.get("length",0.05)
                glColor4f(*self.attributes.get("color",[1,0.5,0,1]))
                glBegin(GL_POINTS)
                glVertex3f(0,0,0)
                glEnd()
                glBegin(GL_LINES)
                glVertex3f(0,0,0)
                glVertex3f(l,0,0)
                glEnd()
            self.displayCache[0].draw(drawRaw,[so3.canonical(item.n),item.x])
        elif isinstance(item,Hold):
            pass
        else:
            itypes = types.objectToTypes(item,world)
            if isinstance(itypes,(list,tuple)):
                #ambiguous, still need to figure out what to draw
                validtypes = []
                for t in itypes:
                    if t == 'Config':
                        if world != None and len(t) == world.robot(0).numLinks():
                            validtypes.append(t)
                    elif t=='Vector3':
                        validtypes.append(t)
                    elif t=='RigidTransform':
                        validtypes.append(t)
                if len(validtypes) > 1:
                    print "Unable to draw item of ambiguous types",validtypes
                    return
                if len(validtypes) == 0:
                    print "Unable to draw any of types",itypes
                    return
                itypes = validtypes[0]
            if itypes == 'Config':
                if world:
                    robot = world.robot(0)
                    if not self.useDefaultAppearance:
                        oldAppearance = [robot.link(i).appearance().clone() for i in xrange(robot.numLinks())]
                        for i in xrange(robot.numLinks()):
                            robot.link(i).appearance().set(self.customAppearance)

                    oldconfig = robot.getConfig()
                    robot.setConfig(item)
                    robot.drawGL()
                    robot.setConfig(oldconfig)
                    if not self.useDefaultAppearance:
                        for (i,app) in enumerate(oldAppearance):
                            robot.link(i).appearance().set(app)
                else:
                    print "Unable to draw Config's without a world"
            elif itypes == 'Vector3':
                def drawRaw():
                    glDisable(GL_LIGHTING)
                    glEnable(GL_POINT_SMOOTH)
                    glPointSize(self.attributes.get("size",5.0))
                    glColor4f(*self.attributes.get("color",[0,0,0,1]))
                    glBegin(GL_POINTS)
                    glVertex3f(0,0,0)
                    glEnd()
                self.displayCache[0].draw(drawRaw,[so3.identity(),item])
                if name != None:
                    self.drawText(name,vectorops.add(item,[0,0,-0.05]))
            elif itypes == 'RigidTransform':
                def drawRaw():
                    gldraw.xform_widget(se3.identity(),self.attributes.get("length",0.1),self.attributes.get("width",0.01))
                self.displayCache[0].draw(drawRaw,transform=item)
                if name != None:
                    self.drawText(name,se3.apply(item,[-0.05]*3))
            elif itypes == 'IKGoal':
                if hasattr(item,'robot'):
                    #need this to be built with a robot element.
                    #Otherwise, can't determine the correct transforms
                    robot = item.robot
                elif world:
                    if world.numRobots() >= 1:
                        robot = world.robot(0)
                    else:
                        robot = None
                else:
                    robot = None
                if robot != None:
                    link = robot.link(item.link())
                    dest = robot.link(item.destLink()) if item.destLink()>=0 else None
                    while len(self.displayCache) < 3:
                        self.displayCache.append(CachedGLObject())
                    self.displayCache[1].name = self.name+" target position"
                    self.displayCache[2].name = self.name+" curve"
                    if item.numPosDims() != 0:
                        lp,wp = item.getPosition()
                        #set up parameters of connector
                        p1 = se3.apply(link.getTransform(),lp)
                        if dest != None:
                            p2 = se3.apply(dest.getTransform(),wp)
                        else:
                            p2 = wp
                        d = vectorops.distance(p1,p2)
                        v1 = [0.0]*3
                        v2 = [0.0]*3
                        if item.numRotDims()==3: #full constraint
                            R = item.getRotation()
                            def drawRaw():
                                gldraw.xform_widget(se3.identity(),self.attributes.get("length",0.1),self.attributes.get("width",0.01))
                            t1 = se3.mul(link.getTransform(),(so3.identity(),lp))
                            t2 = (R,wp) if dest==None else se3.mul(dest.getTransform(),(R,wp))
                            self.displayCache[0].draw(drawRaw,transform=t1)
                            self.displayCache[1].draw(drawRaw,transform=t2)
                            vlen = d*0.1
                            v1 = so3.apply(t1[0],[-vlen]*3)
                            v2 = so3.apply(t2[0],[vlen]*3)
                        elif item.numRotDims()==0: #point constraint
                            def drawRaw():
                                glDisable(GL_LIGHTING)
                                glEnable(GL_POINT_SMOOTH)
                                glPointSize(self.attributes.get("size",5.0))
                                glColor4f(*self.attributes.get("color",[0,0,0,1]))
                                glBegin(GL_POINTS)
                                glVertex3f(0,0,0)
                                glEnd()
                            self.displayCache[0].draw(drawRaw,transform=(so3.identity(),p1))
                            self.displayCache[1].draw(drawRaw,transform=(so3.identity(),p2))
                            #set up the connecting curve
                            vlen = d*0.5
                            d = vectorops.sub(p2,p1)
                            v1 = vectorops.mul(d,0.5)
                            #curve in the destination
                            v2 = vectorops.cross((0,0,0.5),d)
                        else: #hinge constraint
                            p = [0,0,0]
                            d = [0,0,0]
                            def drawRawLine():
                                glDisable(GL_LIGHTING)
                                glEnable(GL_POINT_SMOOTH)
                                glPointSize(self.attributes.get("size",5.0))
                                glColor4f(*self.attributes.get("color",[0,0,0,1]))
                                glBegin(GL_POINTS)
                                glVertex3f(*p)
                                glEnd()
                                glColor4f(*self.attributes.get("color",[0.5,0,0.5,1]))
                                glLineWidth(self.attributes.get("width",3.0))
                                glBegin(GL_LINES)
                                glVertex3f(*p)
                                glVertex3f(*vectorops.madd(p,d,self.attributes.get("length",0.1)))
                                glEnd()
                                glLineWidth(1.0)
                            ld,wd = item.getRotationAxis()
                            p = lp
                            d = ld
                            self.displayCache[0].draw(drawRawLine,transform=link.getTransform(),parameters=(p,d))
                            p = wp
                            d = wd
                            self.displayCache[1].draw(drawRawLine,transform=dest.getTransform() if dest else se3.identity(),parameters=(p,d))
                            #set up the connecting curve
                            d = vectorops.sub(p2,p1)
                            v1 = vectorops.mul(d,0.5)
                            #curve in the destination
                            v2 = vectorops.cross((0,0,0.5),d)
                        def drawConnection():
                            glDisable(GL_DEPTH_TEST)
                            glDisable(GL_LIGHTING)
                            glColor3f(1,0.5,0)
                            gldraw.hermite_curve(p1,v1,p2,v2,0.03)
                            glEnable(GL_DEPTH_TEST)
                        self.displayCache[2].draw(drawConnection,transform=None,parameters = (p1,v1,p2,v2))
                        if name != None:
                            self.drawText(name,vectorops.add(wp,[-0.05]*3))
                    else:
                        wp = link.getTransform()[1]
                        if item.numRotDims()==3: #full constraint
                            R = item.getRotation()
                            def drawRaw():
                                gldraw.xform_widget(se3.identity(),self.attributes.get("length",0.1),self.attributes.get("width",0.01))
                            self.displayCache[0].draw(drawRaw,transform=link.getTransform())
                            self.displayCache[1].draw(drawRaw,transform=se3.mul(link.getTransform(),(R,[0,0,0])))
                        elif item.numRotDims() > 0:
                            #axis constraint
                            d = [0,0,0]
                            def drawRawLine():
                                glDisable(GL_LIGHTING)
                                glColor4f(*self.attributes.get("color",[0.5,0,0.5,1]))
                                glLineWidth(self.attributes.get("width",3.0))
                                glBegin(GL_LINES)
                                glVertex3f(0,0,0)
                                glVertex3f(*vectorops.mul(d,self.attributes.get("length",0.1)))
                                glEnd()
                                glLineWidth(1.0)
                            ld,wd = item.getRotationAxis()
                            d = ld
                            self.displayCache[0].draw(drawRawLine,transform=link.getTransform(),parameters=d)
                            d = wd
                            self.displayCache[1].draw(drawRawLine,transform=(dest.getTransform()[0] if dest else so3.identity(),wp),parameters=d)
                        else:
                            #no drawing
                            pass
                        if name != None:
                            self.drawText(name,se3.apply(wp,[-0.05]*3))
            else:
                print "Unable to draw item of type",itypes

        #revert appearance
        if not self.useDefaultAppearance and hasattr(item,'appearance'):
            item.appearance().set(self.oldAppearance)


class VisualizationPlugin(GLProgramInterface):
    def __init__(self):
        GLProgramInterface.__init__(self)
        self.items = {}
        self.labels = []
        self.t = time.time()
        self.animate = True
        self.animationTime = 0

    def initialize(self):
        return True

    def addLabel(self,text,point,color):
        for (p,textList,pcolor) in self.labels:
            if pcolor == color and vectorops.distance(p,point) < 0.1:
                textList.append(text)
                return
        self.labels.append((point,[text],color))

    def display(self):
        self.labels = []
        world = self.items.get('world',None)
        if world != None: world=world.item
        for (k,v) in self.items.iteritems():
            v.widget = self
            #do animation updates
            v.update(self.animationTime)
            v.swapDrawConfig()
            v.draw(world)
            v.swapDrawConfig()
            v.widget = None #allows garbage collector to delete these objects
        for (p,textlist,color) in self.labels:
            self._drawLabelRaw(p,textlist,color)

    def _drawLabelRaw(self,point,textList,color):
        #assert not self.makingDisplayList,"drawText must be called outside of display list"
        assert self.window != None
        for i,text in enumerate(textList):
            if i+1 < len(textList): text = text+","
            glDisable(GL_LIGHTING)
            glDisable(GL_DEPTH_TEST)
            glColor3f(*color)
            self.draw_text(point,text,size=10)
            glEnable(GL_DEPTH_TEST)
            point = vectorops.add(point,[0,0,-0.05])

    def _clearDisplayLists(self):
        for i in self.items.itervalues():
            i.clearDisplayLists()

    def idlefunc(self):
        oldt = self.t
        self.t = time.time()
        if self.animate:
            self.animationTime += (self.t - oldt)
        return False

    def dirty(self,item_name='all'):
        global _globalLock
        _globalLock.acquire()
        if item_name == 'all':
            if (name,itemvis) in self.items.iteritems():
                itemvis.markChanged()
        else:
            self.items[item_name].markChanged()
        _globalLock.release()

    def clear(self):
        global _globalLock
        _globalLock.acquire()
        for (name,itemvis) in self.items.iteritems():
            itemvis.destroy()
        self.items = {}
        _globalLock.release()


    def add(self,name,item,keepAppearance=False):
        global _globalLock
        _globalLock.acquire()
        if keepAppearance and name in self.items:
            self.items[name].setItem(item)
        else:
            #need to erase prior item visualizer
            if name in self.items:
                self.items[name].destroy()
            app = VisAppearance(item,name)
        self.items[name] = app
        _globalLock.release()

    def animate(self,name,animation,speed=1.0):
        global _globalLock
        _globalLock.acquire()
        if hasattr(animation,'__iter__'):
            #a list of milestones -- loop through them with 1s delay
            print "visualization.animate(): Making a Trajectory with unit durations between",len(animation),"milestones"
            animation = Trajectory(range(len(animation)),animation)
        self.items[name].animation = animation
        self.items[name].animationStartTime = self.animationTime
        self.items[name].animationSpeed = speed
        self.items[name].markChanged()
        _globalLock.release()

    def pauseAnimation(self,paused=True):
        global _globalLock
        _globalLock.acquire()
        self.animate = not paused
        _globalLock.release()

    def stepAnimation(self,amount):
        global _globalLock
        _globalLock.acquire()
        self.animationTime += amount
        _globalLock.release()

    def animationTime(self,newtime=None):
        global _globalLock
        if self==None:
            print "Visualization disabled"
            return 0
        if newtime != None:
            _globalLock.acquire()
            self.animationTime = newtime
            _globalLock.release()
        return self.animationTime

    def remove(self,name):
        global _globalLock
        _globalLock.acquire()
        self.items[name].destroy()
        del self.items[name]
        _globalLock.release()

    def getItemConfig(self,name):
        global _globalLock
        _globalLock.acquire()
        res = config.getConfig(self.items[name].item)
        _globalLock.release()
        return res

    def setItemConfig(self,name,value):
        global _globalLock
        _globalLock.acquire()
        config.getConfig(self.items[name].value,item)
        _globalLock.release()

    def hideLabel(self,name,hidden=True):
        global _globalLock
        _globalLock.acquire()
        self.items[name].attributes["text_hidden"] = hidden
        self.items[name].markChanged()
        _globalLock.release()

    def hide(self,name,hidden=True):
        global _globalLock
        _globalLock.acquire()
        self.items[name].hidden = hidden
        _globalLock.release()

    def setAppearance(self,name,appearance):
        global _globalLock
        _globalLock.acquire()
        self.items[name].useDefaultAppearance = False
        self.items[name].customAppearance = appearance
        self.items[name].markChanged()
        _globalLock.release()

    def setAttribute(self,name,attr,value):
        global _globalLock
        _globalLock.acquire()
        self.items[name].attributes[attr] = value
        if value==None:
            del self.items[name].attributes[attr]
        self.items[name].markChanged()
        _globalLock.release()

    def revertAppearance(self,name):
        global _globalLock
        _globalLock.acquire()
        self.items[name].useDefaultApperance = True
        self.items[name].markChanged()
        _globalLock.release()

    def setColor(self,name,r,g,b,a=1.0):
        global _globalLock
        _globalLock.acquire()
        self.items[name].attributes["color"] = [r,g,b,a]
        self.items[name].useDefaultAppearance = False
        self.items[name].markChanged()
        _globalLock.release()



_vis = VisualizationPlugin()        
_frontend.setPlugin(_vis)

#signals to visualization thread
_quit = False
_thread_running = False

if _PyQtAvailable:
    #Qt specific startup
    #need to set up a QDialog and an QApplication
    class _MyDialog(QDialog):
        def __init__(self,windowinfo):
            QDialog.__init__(self)
            self.widget = windowinfo.window
            self.widget.setMinimumSize(640,480)
            self.widget.setMaximumSize(4000,4000)
            self.widget.setSizePolicy(QSizePolicy(QSizePolicy.Maximum,QSizePolicy.Maximum))

            self.description = QLabel("Press OK to continue")
            self.layout = QVBoxLayout(self)
            self.layout.addWidget(self.widget)
            self.layout.addWidget(self.description)
            self.buttons = QDialogButtonBox(QDialogButtonBox.Ok,Qt.Horizontal, self)
            self.buttons.accepted.connect(self.accept)
            self.layout.addWidget(self.buttons)
            self.setWindowTitle(windowinfo.name)
        def accept(self):
            print "Closing dialog"
            self.widget.close()
            self.widget.setParent(None)
            QDialog.accept(self)
        def reject(self):
            print "Closing dialog"
            self.widget.close()
            self.widget.setParent(None)
            QDialog.reject(self)

    class _MyWindow(QMainWindow):
        def __init__(self,windowinfo):
            QMainWindow.__init__(self)
            self.windowinfo = windowinfo
            self.widget = windowinfo.window
            self.widget.setMinimumSize(640,480)
            self.widget.setMaximumSize(4000,4000)
            self.widget.setSizePolicy(QSizePolicy(QSizePolicy.Maximum,QSizePolicy.Maximum))
            self.setCentralWidget(self.widget)
            self.setWindowTitle(windowinfo.name)
        def closeEvent(self,event):
            self.windowinfo.mode = 'hidden'
            self.widget.close()
            self.widget.setParent(None)
            print "Closing window"
            self.hide()

    def _run_app_thread():
        global _thread_running,_vis,_widget,_window,_quit,_showdialog,_showwindow,_window_title
        global _custom_run_method,_custom_run_retval
        _thread_running = True
        #Do Qt setup
        _app = _GLBackend.initialize("Klamp't visualization")

        #res = _app.exec_()
        res = None
        while not _quit:
            _globalLock.acquire()
            for w in _windows:
                if w.window == None and w.mode != 'hidden':
                    w.window = _GLBackend.createWindow(w.name)
                    w.window.setPlugin(w.frontend)
                if w.mode == 'dialog' and w.guidata == None:
                    w.guidata = _MyDialog(w)
                    _globalLock.release()
                    res = w.guidata.exec_()
                    _globalLock.acquire()
                    w.guidata = None
                    w.window = None
                    w.mode = 'hidden'
                if w.mode == 'shown' and w.guidata == None:
                    w.guidata = _MyWindow(w)
                if w.mode == 'shown' and not w.guidata.isVisible():
                    w.guidata.show()
                if w.mode == 'hidden' and w.guidata != None and w.guidata.isVisible():
                    w.guidata.hide()
                    w.window = None
                    w.guidata = None
            
            _GLBackend.app.processEvents()
            _globalLock.release()
            time.sleep(0.001)
        print "Visualization thread closing..."
        for w in _windows:
            w.vis.clear()
        _thread_running = False
        return res


elif _GLUTAvailable:
    print "klampt.visualization: QT is not available, falling back to poorer"
    print "GLUT interface.  Returning to another GLUT thread will not work"
    print "properly."
    print ""
    
    class GLUTHijacker(glinterface.GLProgramInterface):
        def __init__(self,windowinfo):
            glinterface.GLProgramInterface.__init__(self)
            self.windowinfo = windowinfo
            self.name = windowinfo.name
            self.frontend = windowinfo.frontend
            self.inDialog = False
        def initialize(self):
            if not self.frontend.initialize(self): return False
            GLPluginProgram.initialize(self)
            return True
        def display(self):
            global _globalLock
            _globalLock.acquire()
            self.frontend.display(self)
            _globalLock.release()
            return True
        def display_screen(self):
            global _globalLock
            _globalLock.acquire()
            self.frontend.display_screen(self)
            glColor3f(1,1,1)
            glRasterPos(20,50)
            gldraw.glutBitmapString(GLUT_BITMAP_HELVETICA_18,"(Do not close this window except to quit)")
            if self.inDialog:
                glColor3f(1,1,0)
                glRasterPos(20,80)
                gldraw.glutBitmapString(GLUT_BITMAP_HELVETICA_18,"In Dialog mode. Press 'q' to return to normal mode")
            _globalLock.release()
        def keyboardfunc(self,c,x,y):
            if self.inDialog and c=='q':
                print "Q pressed, hiding dialog"
                self.inDialog = False
                global _globalLock
                _globalLock.acquire()
                self.windowinfo.mode = 'hidden'
                glutIconifyWindow()
                _globalLock.release()
            else:
                GLPluginProgram.keyboardfunc(self,c,x,y)

        def idlefunc(self):
            global _quit,_showdialog
            global _globalLock
            _globalLock.acquire()
            if _quit:
                if bool(glutLeaveMainLoop):
                    glutLeaveMainLoop()
                else:
                    print "Not compiled with freeglut, can't exit main loop safely. Press Ctrl+C instead"
                    raw_input()
            if not self.inDialog:
                if self.windowinfo.mode == 'shown':
                    glutShowWindow()
                elif self.windowinfo.mode == 'dialog':
                    self.inDialog = True
                    glutShowWindow()
                else:
                    glutIconifyWindow()
            _globalLock.release()
            GLPluginProgram.idlefunc(self)


    def _run_app_thread():
        global _thread_running,_app,_vis,_old_glut_window,_quit
        _thread_running = True
        _GLBackend.initialize("Klamp't visualization")
        _GLBackend.addPlugin(GLUTHijacker(windows[0]))
        _GLBackend.run()
        print "Visualization thread closing..."
        for w in _windows:
            w.vis.clear()
        _thread_running = False
        return
    
def _kill():
    global _quit
    _quit = True
    while _thread_running:
        time.sleep(0.01)

def _show():
    global _windows,_current_window,_thread_running
    if len(_windows)==0:
        _windows.append(WindowInfo(_window_title,_frontend,_vis)) 
        _current_window = 0
    if not _thread_running:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        thread = Thread(target=_run_app_thread)
        thread.setDaemon(True)
        thread.start()
    _windows[_current_window].mode = 'shown'

def _hide():
    global _windows,_current_window,_thread_running
    if _current_window == None:
        return
    _windows[_current_window].mode = 'hidden'

def _dialog():
    global _windows,_current_window,_thread_running
    if len(_windows)==0:
        _windows.append(WindowInfo(_window_title,_frontend,_vis,None))
        _current_window = 0
    if not _thread_running:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        thread = Thread(target=_run_app_thread)
        thread.start()
    _windows[_current_window].mode = 'dialog'
    while _windows[_current_window].mode == 'dialog':
        time.sleep(0.1)
    return

def _onFrontendChange():
    global _windows,_current_window,_thread_running
    if _current_window == None:
        return
    _windows[_current_window].frontend = _frontend
    if _windows[_current_window].window:
        _windows[_current_window].setPlugin(frontend)