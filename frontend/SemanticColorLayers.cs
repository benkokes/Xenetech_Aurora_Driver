// Offline coverage layers identified by the source brush, before RGB blending.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Aurora.Frontend
{
    public sealed class SemanticColorLayer
    {
        public string color;
        public int palette_index;
        public ExposureReport coverage;
    }

    public sealed class SemanticColorReport
    {
        public string status = "prepared_offline_flat_color_layers";
        public string encoding = "source-brush-coverage-u8-review-only";
        public string limitation = "White paint excluded; bitmap, gradient and transparent color classification remain unsupported.";
        public bool white_paint_excluded;
        public string unsupported_reason;
        public List<SemanticColorLayer> layers = new List<SemanticColorLayer>();
    }

    internal static class SemanticColorLayers
    {
        static readonly int[] Palette = {0x000000,0xff0000,0x000080,0xff00ff,0x800000,0x00ff00,0x808000,0x00ffff,
            0x808080,0x0000ff,0x800080,0xc0c0c0,0x008000,0xffff00,0x008080,0xffffff};
        static int Index(int rgb) {return Array.IndexOf(Palette,rgb);}
        static int Rgb(Color color) {return (color.R<<16)|(color.G<<8)|color.B;}

        static void BrushColor(Brush brush, HashSet<int> colors)
        {
            if(brush==null)return;
            SolidColorBrush solid=brush as SolidColorBrush;
            if(solid==null)throw new NotSupportedException("Color layers require flat solid brushes; images and gradients need separate validation.");
            if(solid.Opacity!=1 || solid.Color.A!=255)
                throw new NotSupportedException("Transparent color brushes require separate validation.");
            colors.Add(Rgb(solid.Color));
            if(colors.Count>33)throw new NotSupportedException("Color review exceeds 32 nonwhite brush colors.");
        }

        static void Collect(Drawing drawing, HashSet<int> colors, int depth)
        {
            if(depth>128)throw new NotSupportedException("Color drawing nesting exceeds the review limit.");
            DrawingGroup group=drawing as DrawingGroup;
            if(group!=null)
            {
                if(group.Opacity!=1 || group.OpacityMask!=null)
                    throw new NotSupportedException("Color groups with transparency or masks require separate validation.");
                foreach(Drawing child in group.Children)Collect(child,colors,depth+1);
                return;
            }
            GeometryDrawing geometry=drawing as GeometryDrawing;
            if(geometry!=null)
            {
                BrushColor(geometry.Brush,colors);
                if(geometry.Pen!=null)BrushColor(geometry.Pen.Brush,colors);
                return;
            }
            GlyphRunDrawing glyph=drawing as GlyphRunDrawing;
            if(glyph!=null){BrushColor(glyph.ForegroundBrush,colors);return;}
            throw new NotSupportedException("Bitmap or unknown drawing content cannot use flat-brush color layers.");
        }

        static Brush MaskBrush(Brush original, int target)
        {
            if(original==null)return null;
            // Other colors remain white OCCLUDERS; dropping their geometry
            // would expose hidden artwork underneath them in a color pass.
            return Rgb(((SolidColorBrush)original).Color)==target?Brushes.Black:Brushes.White;
        }

        static Drawing Recolor(Drawing drawing, int target)
        {
            DrawingGroup group=drawing as DrawingGroup;
            if(group!=null)
            {
                DrawingGroup copy=group.CloneCurrentValue();copy.Children.Clear();
                foreach(Drawing child in group.Children)copy.Children.Add(Recolor(child,target));
                return copy;
            }
            GeometryDrawing geometry=drawing as GeometryDrawing;
            if(geometry!=null)
            {
                GeometryDrawing copy=geometry.CloneCurrentValue();copy.Brush=MaskBrush(geometry.Brush,target);
                if(copy.Pen!=null)copy.Pen.Brush=MaskBrush(geometry.Pen.Brush,target);
                return copy;
            }
            GlyphRunDrawing glyph=(GlyphRunDrawing)drawing;
            GlyphRunDrawing text=glyph.CloneCurrentValue();text.ForegroundBrush=MaskBrush(glyph.ForegroundBrush,target);return text;
        }

        internal static SemanticColorReport Write(Drawing drawing, Size size, double dpi, bool aliasedText,
            int width, int height, string directory, int number)
        {
            SemanticColorReport report=new SemanticColorReport();
            HashSet<int> colors=new HashSet<int>();
            try {Collect(drawing,colors,0);}
            catch(NotSupportedException error)
            {report.status="unsupported_flat_color_layers";report.unsupported_reason=error.Message;return report;}
            report.white_paint_excluded=colors.Remove(0xffffff);
            if(colors.Count>32)
            {report.status="unsupported_flat_color_layers";report.unsupported_reason="Color review exceeds 32 nonwhite brush colors.";return report;}
            if(width<=0 || height<=0 || (long)width*height>15000000)
                throw new ArgumentException("Semantic color layers require a bounded 167-DPI review surface.");
            List<int> order=new List<int>(colors);
            order.Sort(delegate(int a,int b) {
                int ia=Index(a),ib=Index(b);if(ia<0)ia=16;if(ib<0)ib=16;
                int compared=ia.CompareTo(ib);return compared!=0?compared:a.CompareTo(b);
            });
            long total=0;
            foreach(int rgb in order)
            {
                Drawing mask=Recolor(drawing,rgb);
                BitmapSource bitmap=Intake.Render(mask,size,dpi,aliasedText,width,height);
                string file=String.Format(CultureInfo.InvariantCulture,"page-{0:000}-brush-layer-{1:00}.coverage",number,report.layers.Count);
                ExposureReport exposure=ExposureImage.Write(bitmap,directory,number,file);
                if(exposure==null)continue; // Entirely hidden or clipped color.
                total+=(long)exposure.width*exposure.height;
                if(total>50000000)throw new ArgumentException("Semantic coverage layers exceed the 50-megapixel aggregate limit.");
                report.layers.Add(new SemanticColorLayer {color="#FF"+rgb.ToString("X6",CultureInfo.InvariantCulture),
                    palette_index=Index(rgb),coverage=exposure});
            }
            return report;
        }
    }
}
