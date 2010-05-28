#!/usr/bin/env python

# "Hamsterball" simple extensions for Hamster Graphics
# Uses Hamster Graphics library
# http://github.com/tbaugis/hamster_experiments

from hamster import graphics
import cairo, rsvg
from math import sqrt

class SVGTexture:
    '''
    A container for a set of textures generated from an SVG. Multiple textures are used
    so that the quality looks good regardless of size (like opengl 'mipmapping')

    When using SVGTextures, make sure you only create as many as necessary. For example,
    if creating 100 balls with the same source SVG, only use a single SVGTexture for all
    of your sprites. Since the sprites don't alter the SVGTexture's contents, this works.

    This can save a LOT of memory, and loading time, depending on how many sprites you create.

    Also, if SVGs are loaded during program load, rather than sprite creation, this is better for
    the speed of the render
    '''
    def __init__(self, filename, highres=True):
        if highres:
            # Arbitrary values for scale of sprite. Seems to work but is likely too many
            self.__reses = [0.4, 1.0, 2.0, 4.0, 8.0, 16.0]
        else:
            self.__reses = [0.2, 0.4, 1.0, 2.0, 4.0, 8.0]
        self.__reses.sort()

        # Open up the svg file, and get the ratio between its width and height
        svgh = rsvg.Handle(file=filename)
        w = svgh.get_property("width")
        h = svgh.get_property("height")

        self.width = w
        self.height = h

        # Generate a bunch of surfaces from the svg
        self.__textures = {}
        for size in self.__reses:
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w*size), int(h*size))
            c = cairo.Context(s)
            c.scale(size, size)
            svgh.render_cairo(c)
            self.__textures[size] = s

    def get_texture(self, scale_x, scale_y):
        '''Get the smallest texture whose height/width is larger than the specified height/width'''
        # Use whichever is scaled the most
        scale = max([scale_x, scale_y])
        for key in self.__reses:
	        if key > scale:
		        return self.__textures[key], key
        return self.__textures[max(self.__textures)], key


class SVGSprite(graphics.Sprite):
    '''
	A hamster sprite that renders as an SVGTexture rather than a shape.
	Features include automatically choosing which SVGTexture texture to use
	based on scale.

	Scaling is very smooth and can go up to high resolutions.
	'''
    def __init__(self, svg_tex, x = 0, y = 0,
                 opacity = 1, visible = True,
                 rotation = 0, pivot_x = 0, pivot_y = 0,
                 scale_x = 1, scale_y = 1,
                 interactive = False, draggable = False,
                 z_order = 0):
                 
        graphics.Sprite.__init__(self, x, y,
                 opacity, visible,
                 rotation, pivot_x, pivot_y,
                 scale_x, scale_y,
                 interactive, draggable,
                 z_order)
        
        # The SVGTexture this sprite should use
        self.svg_tex = svg_tex
        self.width = self.svg_tex.width
        self.height = self.svg_tex.height
        
        # Get the correct texture given the starting scale
        t, s = self.svg_tex.get_texture(scale_x, scale_y)
        self.texture = t

        self.connect("on-render", self.on_render)
        
    def on_render(self, sprite):
        '''Make sure when overriding to call this so that the SVG Texture is painted'''
        self.graphics.set_source_surface(self.texture)
        self.graphics.paint()

    def _draw(self, context, opacity = 1):
        '''
        Almost a copy and paste of Hamster's Sprite._draw, but does one extra scale, to make
        sure the texture always appears correctly
        '''
        if self.visible is False:
            return

        if any([self.x, self.y, self.rotation, self.scale_x, self.scale_y]):
            context.save()

            if self.x or self.y or self.pivot_x or self.pivot_y:
                context.translate(self.x + self.pivot_x, self.y + self.pivot_y)

            if self.rotation:
                context.rotate(self.rotation)

            if self.pivot_x or self.pivot_y:
                context.translate(-self.pivot_x, -self.pivot_y)

            if self.scale_x != 1 or self.scale_y != 1:
                context.scale(self.scale_x, self.scale_y)

        self.graphics.opacity = self.opacity * opacity
        
        # Begin modifications from regular _draw ###
        # Get the matrix values for the context (we need xx and yy for scale)
        xx, yx, xy, yy, x0, y0 = context.get_matrix()
        # Compute the scale from the matrix values (confuzzling)
        # FIXME: This is based on a guess and seems to work fine. could be wrong!!
        cscale_x = sqrt(xx*xx + xy*xy)
        cscale_y = sqrt(yy*yy + yx*yx)
        
        # Find the correct texture for our scale
        t, s = self.svg_tex.get_texture(cscale_x, cscale_y)
        # Scale the context down for the draw process (we'll have to scale it up again before we send
        # it to the children)
        context.scale(1/s,1/s)
        
        # If we have a new texture we'll need to re-render--integrate this with standard dirtiness so we don't
        # have to render more than necessary
        if self.texture != t:
            self.texture = t
            
        if (self._sprite_dirty): # send signal to redo the drawing when sprite's dirty
            self.emit("on-render")
            self._sprite_dirty = False
            
        self.graphics._draw(context, self.interactive or self.draggable)
        
        # Scale back up for children (they need to come after because otherwise they'll appear under the parent)
        context.scale(s, s)
        ## End modifications to _draw ###
        
        for sprite in self.sprites:
            sprite._draw(context, self.opacity * opacity)  

        if any([self.x, self.y, self.rotation, self.scale_x, self.scale_y]):
            context.restore()

class PhysicsBox(graphics.Sprite):
    '''
    A container derived from a sprite that can hold standard sprites and updates its position
    and rotation based on its physics body position.
    
    Note: you can either add a physics body (self.body) after creating a PhysicsBox, or derive a class from
    PhysicsBox that creates a self.body.
    
    The update function must be called every frame to get the box's new position
    
    PhysicsBoxes are invisible by default but since they are basic sprites you could in theory add graphics
    to them directly, or add children sprites (the best way)
    '''
    def __init__(self, world, x = 0, y = 0,
                 opacity = 1, visible = True,
                 rotation = 0, pivot_x = 0, pivot_y = 0,
                 scale_x = 1, scale_y = 1,
                 interactive = False, draggable = False,
                 z_order = 0):
        graphics.Sprite.__init__(self, x, y, opacity, visible,
                 rotation, pivot_x, pivot_y, scale_x, scale_y,
                 interactive, draggable,
                 z_order)
                 
        self.body = None
        self.world = world

    def _draw(self, context, opacity = 1):
        '''
        Slightly modified draw function to update location of the PhysicsBox before drawing.
        Called automatically by Hamster every frame.
        
        Only moves the sprite automatically if it already has a body assigned to it
        '''
        if self.body:
            pos = self.body.GetPosition()
            # FIXME: dirty hack to get things looking right, not the right way to do it
            self.x = pos.x*25.0
            self.y = -pos.y*25.0
            # Note: negative rotation because the Sprite's coordinate system is opposite on y-axis
            self.rotation = -self.body.GetAngle()
        
        graphics.Sprite._draw(self, context, opacity)

