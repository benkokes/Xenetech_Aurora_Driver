// Offline Microsoft XPS document intake. No spooler changes or device access.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Xps.Packaging;

namespace Aurora.Frontend
{
    public sealed class Options
    {
        public int Dpi = 167;
        public bool AuroraGrid;
        public bool XpGrid;
        public bool CorelXpGrid;
        internal CorelXpLayout CorelLayout;
        public bool AliasedText;
        public bool TiledRaster;
        public bool ColorReview;
        public double RenderDpi { get { return AuroraGrid ? 1000.0 / 6 : Dpi; } }
        public string RasterGrid { get { return CorelXpGrid ? "coreldraw-xp-draft" : XpGrid ? "xp-167-6mil-draft" : AuroraGrid ? "aurora-167-6mil-draft" : "document-dpi"; } }
        public Color? CutColor;
        public bool AnyCutColor;
        public bool CutPathsOnly;
        public double MaxCutWidthMm = 0.1;
        public double FlattenToleranceMm = 0.01;
        public void Validate()
        {
            if (Dpi < 50 || Dpi > 1200) throw new ArgumentException("DPI must be between 50 and 1200.");
            if (TiledRaster && (AuroraGrid || XpGrid || CorelXpGrid))
                throw new ArgumentException("Tiled rendering is currently for document-grid offline previews only.");
            if ((AuroraGrid || XpGrid) && Dpi != 167) throw new ArgumentException("The experimental Aurora/XP grids require nominal DPI 167.");
            if ((AuroraGrid ? 1 : 0) + (XpGrid ? 1 : 0) + (CorelXpGrid ? 1 : 0) > 1) throw new ArgumentException("Choose exactly one raster grid.");
            if (CorelXpGrid && Dpi != 100 && Dpi != 167) throw new ArgumentException("The Corel XP reference profile supports only 100 and 167 DPI.");
            if (!Finite(MaxCutWidthMm) || MaxCutWidthMm <= 0 || MaxCutWidthMm > 1)
                throw new ArgumentException("Maximum cutting stroke width must be greater than zero and at most 1 mm.");
            if (!Finite(FlattenToleranceMm) || FlattenToleranceMm < 0.001 || FlattenToleranceMm > 0.1)
                throw new ArgumentException("Curve tolerance must be between 0.001 and 0.1 mm.");
            if (CutColor.HasValue && CutColor.Value.A != 255) throw new ArgumentException("Cut color must be opaque.");
            if (AnyCutColor && CutColor.HasValue) throw new ArgumentException("Choose a specific cut color or any color.");
            if (CutPathsOnly && (!CorelXpGrid || !AnyCutColor || ColorReview || TiledRaster))
                throw new ArgumentException("Cut-path-only review requires the Corel grid, any stroke color, and no other review mode.");
            if (AnyCutColor && ColorReview) throw new ArgumentException("Choose ordinary all-color cuts or color-layer review.");
            if (ColorReview && (!CorelXpGrid || Dpi != 167 || TiledRaster || CutColor.HasValue))
                throw new ArgumentException("Color review requires the 167-DPI Corel grid and no single cut-color rule.");
        }
        internal static bool Finite(double value) { return !Double.IsNaN(value) && !Double.IsInfinity(value); }
    }

    public sealed class CutPath
    {
        public string color;
        public double width_mm;
        public bool closed;
        public List<double[]> points_mm = new List<double[]>();
    }

    public sealed class PageReport
    {
        public int number;
        public double width_mm, height_mm;
        public int pixel_width, pixel_height;
        public int preview_x_pixels, preview_y_pixels;
        public long engraving_nonwhite_pixels;
        public bool has_visible_artwork;
        public ExposureReport exposure;
        public ColorReviewReport color_raster_review;
        public SemanticColorReport color_layers;
        public int geometry_drawings, glyph_drawings, image_drawings, image_brushes, removed_cut_strokes;
        public string engraving_png, cuts_svg;
        public List<CutPath> cuts = new List<CutPath>();
        public List<string> review_reasons = new List<string>();
    }

    public sealed class IntakeReport
    {
        public int schema_version = 2;
        public string status = "offline_preview_only";
        public string source_sha256;
        public string source_format = "Microsoft XPS";
        public string source_file = "source.bin";
        public string normalized_file;
        public string coordinate_system = "millimeters, page top-left, x right, y down";
        public int dpi;
        public double render_dpi;
        public string raster_grid;
        public string text_rendering;
        public bool tiled_raster;
        public bool cut_paths_only;
        public CorelXpReport corel_xp_compatibility;
        public string cut_color;
        public double max_cut_width_mm, flatten_tolerance_mm;
        public List<PageReport> pages = new List<PageReport>();
    }

    public static class Intake
    {
        static Drawing AliasedTextOutlines(Drawing drawing)
        {
            GlyphRunDrawing glyph = drawing as GlyphRunDrawing;
            if (glyph != null)
            {
                DrawingGroup text = new DrawingGroup();
                RenderOptions.SetEdgeMode(text, EdgeMode.Aliased);
                text.Children.Add(new GeometryDrawing(glyph.ForegroundBrush, null, glyph.GlyphRun.BuildGeometry()));
                return text;
            }
            DrawingGroup group = drawing as DrawingGroup;
            if (group == null) return drawing;
            DrawingGroup copy = group.CloneCurrentValue();
            copy.Children.Clear();
            foreach (Drawing child in group.Children) copy.Children.Add(AliasedTextOutlines(child));
            return copy;
        }
        internal const double MmPerDip = 25.4 / 96.0;
        const long MaxPixels = 50000000;

        // Each visual's drawing excludes its visual children. Preserve both trees,
        // along with local transforms, clips, offsets and opacity for WPF rendering.
        internal static DrawingGroup Capture(Visual visual)
        {
            if (VisualTreeHelper.GetEffect(visual) != null)
                throw new NotSupportedException("Visual effects require separate validation.");
            DrawingGroup group = new DrawingGroup();
            Transform transform = VisualTreeHelper.GetTransform(visual);
            Matrix matrix = transform == null ? Matrix.Identity : transform.Value;
            Vector offset = VisualTreeHelper.GetOffset(visual);
            matrix.Translate(offset.X, offset.Y);
            group.Transform = new MatrixTransform(matrix);
            group.ClipGeometry = VisualTreeHelper.GetClip(visual);
            group.Opacity = VisualTreeHelper.GetOpacity(visual);
            group.OpacityMask = VisualTreeHelper.GetOpacityMask(visual);
            DrawingGroup own = VisualTreeHelper.GetDrawing(visual);
            if (own != null) group.Children.Add(own.CloneCurrentValue());
            for (int i = 0; i < VisualTreeHelper.GetChildrenCount(visual); i++)
            {
                Visual child = VisualTreeHelper.GetChild(visual, i) as Visual;
                if (child == null) throw new NotSupportedException("Non-2D visual content is unsupported.");
                group.Children.Add(Capture(child));
            }
            return group;
        }

        internal static Geometry InPage(Geometry geometry, Matrix world)
        {
            Geometry copy = geometry.CloneCurrentValue();
            Matrix matrix = copy.Transform == null ? Matrix.Identity : copy.Transform.Value;
            matrix.Append(world);
            copy.Transform = new MatrixTransform(matrix);
            return copy;
        }

        static double MaximumScale(Matrix m)
        {
            double a = m.M11 * m.M11 + m.M12 * m.M12;
            double b = m.M21 * m.M21 + m.M22 * m.M22;
            double c = m.M11 * m.M21 + m.M12 * m.M22;
            return Math.Sqrt((a + b + Math.Sqrt((a - b) * (a - b) + 4 * c * c)) / 2);
        }

        static void Review(PageReport report, string reason)
        {
            if (!report.review_reasons.Contains(reason)) report.review_reasons.Add(reason);
        }

        internal static void Separate(Drawing drawing, Matrix parent, List<Geometry> inheritedClips,
                                      bool opaque, PageReport report, Options options)
        {
            DrawingGroup group = drawing as DrawingGroup;
            if (group != null)
            {
                Matrix world = group.Transform == null ? Matrix.Identity : group.Transform.Value;
                world.Append(parent);
                List<Geometry> clips = new List<Geometry>(inheritedClips);
                if (group.ClipGeometry != null) clips.Add(InPage(group.ClipGeometry, world));
                bool childOpaque = opaque && group.Opacity == 1 && group.OpacityMask == null;
                foreach (Drawing child in group.Children) Separate(child, world, clips, childOpaque, report, options);
                return;
            }
            if (drawing is GlyphRunDrawing) { report.glyph_drawings++; return; }
            if (drawing is ImageDrawing) { report.image_drawings++; return; }
            GeometryDrawing shape = drawing as GeometryDrawing;
            if (shape == null) throw new NotSupportedException("Unsupported drawing type: " + drawing.GetType().Name);
            report.geometry_drawings++;
            if (shape.Brush is ImageBrush) report.image_brushes++;
            if (shape.Pen != null && shape.Pen.Brush is ImageBrush) report.image_brushes++;
            if ((!options.CutColor.HasValue && !options.AnyCutColor && !options.ColorReview) || shape.Pen == null) return;
            SolidColorBrush brush = shape.Pen.Brush as SolidColorBrush;
            if (brush == null || (!options.AnyCutColor && !options.ColorReview && brush.Color != options.CutColor.Value)) return;
            double widthMm = Math.Abs(shape.Pen.Thickness) * MaximumScale(parent) * MmPerDip;
            if (widthMm > options.MaxCutWidthMm) return;
            if (!opaque || brush.Color.A != 255 || brush.Opacity != 1 || shape.Pen.DashStyle.Dashes.Count != 0)
            {
                Review(report, "A matching thin stroke uses transparency, a mask, or dashes; retained in engraving preview.");
                return;
            }
            Geometry geometry = InPage(shape.Geometry, parent);
            Geometry outline = InPage(shape.Geometry.GetWidenedPathGeometry(shape.Pen), parent);
            foreach (Geometry clip in inheritedClips)
            {
                if (clip.FillContainsWithDetail(outline) != IntersectionDetail.FullyContains)
                {
                    Review(report, "A matching thin stroke crosses a clip or page boundary; retained in engraving preview.");
                    return;
                }
            }
            // Apply the full page transform before flattening, so the tolerance is
            // measured in page units even with nested, nonuniform scale/rotation.
            PathGeometry flat = geometry.GetFlattenedPathGeometry(options.FlattenToleranceMm / MmPerDip, ToleranceType.Absolute);
            Matrix flatTransform = flat.Transform == null ? Matrix.Identity : flat.Transform.Value;
            List<CutPath> paths = new List<CutPath>();
            foreach (PathFigure figure in flat.Figures)
            {
                CutPath path = NewPath(brush.Color, widthMm, flatTransform.Transform(figure.StartPoint));
                bool gap = false;
                foreach (PathSegment segment in figure.Segments)
                {
                    List<Point> points = new List<Point>();
                    LineSegment line = segment as LineSegment;
                    PolyLineSegment poly = segment as PolyLineSegment;
                    if (line != null) points.Add(line.Point);
                    else if (poly != null) points.AddRange(poly.Points);
                    else throw new NotSupportedException("Flattened geometry contains a curve.");
                    foreach (Point local in points)
                    {
                        Point point = flatTransform.Transform(local);
                        if (segment.IsStroked) path.points_mm.Add(ToMm(point));
                        else
                        {
                            if (path.points_mm.Count > 1) paths.Add(path);
                            path = NewPath(brush.Color, widthMm, point);
                            gap = true;
                        }
                    }
                }
                // Closing is a real stroke even when a figure has unstroked gaps.
                if (figure.IsClosed)
                {
                    if (gap) path.points_mm.Add(ToMm(flatTransform.Transform(figure.StartPoint)));
                    else path.closed = true;
                }
                if (path.points_mm.Count > 1) paths.Add(path);
            }
            if (paths.Count == 0) return;
            report.cuts.AddRange(paths);
            report.removed_cut_strokes++;
            shape.Pen = null; // A fill on this same shape stays in the engraving layer.
        }

        static CutPath NewPath(Color color, double width, Point point)
        {
            CutPath path = new CutPath { color = color.ToString(), width_mm = width };
            path.points_mm.Add(ToMm(point));
            return path;
        }
        static double[] ToMm(Point point) { return new double[] { point.X * MmPerDip, point.Y * MmPerDip }; }

        internal static BitmapSource Render(Drawing drawing, Size size, double dpi, bool aliasedText = false, int surfaceWidth = 0, int surfaceHeight = 0)
        {
            int width = surfaceWidth == 0 ? checked((int)Math.Ceiling(size.Width * dpi / 96.0)) : surfaceWidth;
            int height = surfaceHeight == 0 ? checked((int)Math.Ceiling(size.Height * dpi / 96.0)) : surfaceHeight;
            if (width <= 0 || height <= 0 || (long)width * height > MaxPixels)
                throw new ArgumentException("Page raster exceeds the 50 megapixel limit or has invalid dimensions.");
            DrawingVisual visual = new DrawingVisual();
            if (aliasedText) drawing = AliasedTextOutlines(drawing);
            using (DrawingContext dc = visual.RenderOpen())
            {
                // Cover the entire rounded-up raster, including fractional page
                // edges. Otherwise a partly transparent white edge appears gray
                // in premultiplied pixels and falsely counts as page artwork.
                dc.DrawRectangle(Brushes.White, null, new Rect(0, 0, width * 96.0 / dpi, height * 96.0 / dpi));
                dc.PushClip(new RectangleGeometry(new Rect(size)));
                dc.DrawDrawing(drawing);
                dc.Pop();
            }
            RenderTargetBitmap bitmap = new RenderTargetBitmap(width, height, dpi, dpi, PixelFormats.Pbgra32);
            bitmap.Render(visual);
            return bitmap;
        }

        internal static PageReport ProcessPage(Visual visual, Size size, int number, string directory, Options options)
        {
            if (!Options.Finite(size.Width) || !Options.Finite(size.Height) || size.Width <= 0 || size.Height <= 0)
                throw new ArgumentException("Invalid page dimensions.");
            if (!options.TiledRaster && Math.Ceiling(size.Width * options.RenderDpi / 96.0) * Math.Ceiling(size.Height * options.RenderDpi / 96.0) > MaxPixels)
                throw new ArgumentException("Page raster exceeds the 50 megapixel limit.");
            DrawingGroup drawing = Capture(visual);
            PageReport report = new PageReport { number = number, width_mm = size.Width * MmPerDip, height_mm = size.Height * MmPerDip };
            Separate(drawing, Matrix.Identity, new List<Geometry> { new RectangleGeometry(new Rect(size)) }, true, report, options);
            if (options.CutPathsOnly)
            {
                options.CorelLayout.CheckPage(size);
                report.pixel_width=options.CorelLayout.Width;
                report.pixel_height=options.CorelLayout.Height;
                report.has_visible_artwork=report.cuts.Count>0;
                report.cuts_svg=String.Format(CultureInfo.InvariantCulture,"page-{0:000}-cuts.svg",number);
                WriteSvg(Path.Combine(directory,report.cuts_svg),report);
                return report;
            }
            BitmapSource bitmap;
            Drawing rasterDrawing=drawing;
            int originX=0,originY=0;
            if(options.TiledRaster)
                bitmap=RenderTiled(drawing,size,options.RenderDpi,options.AliasedText,out originX,out originY);
            else if (options.CorelXpGrid)
            {
                CorelXpLayout layout = options.CorelLayout;
                if (layout == null) throw new ArgumentException("Corel layout requires measured source printer DPI.");
                layout.CheckPage(size);
                DrawingGroup shifted = new DrawingGroup { Transform = new TranslateTransform(layout.ShiftX, layout.ShiftY) };
                shifted.Children.Add(drawing);
                rasterDrawing=shifted;
                if (CorelClipsEngraving(shifted, size, layout, options.AliasedText))
                    Review(report, "Corel XP placement would clip engraving at the legacy surface boundary.");
                bitmap = Render(shifted, size, options.RenderDpi, options.AliasedText, layout.Width, layout.Height);
            }
            else bitmap = Render(drawing, size, options.RenderDpi, options.AliasedText);
            report.pixel_width = options.TiledRaster ? checked((int)Math.Ceiling(size.Width*options.RenderDpi/96)) : bitmap.PixelWidth;
            report.pixel_height = options.TiledRaster ? checked((int)Math.Ceiling(size.Height*options.RenderDpi/96)) : bitmap.PixelHeight;
            report.preview_x_pixels=originX;report.preview_y_pixels=originY;
            byte[] scan = new byte[bitmap.PixelWidth * 4];
            for (int row = 0; row < bitmap.PixelHeight; row++)
            {
                bitmap.CopyPixels(new Int32Rect(0, row, bitmap.PixelWidth, 1), scan, scan.Length, 0);
                for (int x = 0; x < scan.Length; x += 4)
                    if (scan[x] < 255 || scan[x + 1] < 255 || scan[x + 2] < 255) report.engraving_nonwhite_pixels++;
            }
            report.has_visible_artwork = report.engraving_nonwhite_pixels > 0 || report.cuts.Count > 0;
            report.exposure = ExposureImage.Write(bitmap, directory, number);
            if(report.exposure!=null) {report.exposure.x_pixels+=originX;report.exposure.y_pixels+=originY;}
            if (options.ColorReview)
            {
                report.color_raster_review = ColorReviewImage.Write(bitmap,directory,number);
                report.color_layers = SemanticColorLayers.Write(rasterDrawing,size,options.RenderDpi,options.AliasedText,
                    bitmap.PixelWidth,bitmap.PixelHeight,directory,number);
                if(report.color_layers.status!="prepared_offline_flat_color_layers")
                    Review(report,"Semantic color layers held: "+report.color_layers.unsupported_reason);
                if (report.color_raster_review != null)
                {
                    report.color_raster_review.x_pixels += originX;
                    report.color_raster_review.y_pixels += originY;
                }
                Review(report,"Experimental color review: nonwhite coverage cannot distinguish white artwork; per-color output remains held.");
            }
            if (!report.has_visible_artwork)
                Review(report, "The captured page has no visible artwork. Check media size, placement, and print range before generating a laser job.");
            report.engraving_png = String.Format(CultureInfo.InvariantCulture, "page-{0:000}-engraving.png", number);
            report.cuts_svg = String.Format(CultureInfo.InvariantCulture, "page-{0:000}-cuts.svg", number);
            PngBitmapEncoder encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(bitmap));
            using (FileStream file = new FileStream(Path.Combine(directory, report.engraving_png), FileMode.CreateNew)) encoder.Save(file);
            WriteSvg(Path.Combine(directory, report.cuts_svg), report);
            return report;
        }

        internal static BitmapSource RenderTiled(Drawing drawing,Size size,double dpi,bool aliasedText,out int originX,out int originY)
        {
            int width=checked((int)Math.Ceiling(size.Width*dpi/96)),height=checked((int)Math.Ceiling(size.Height*dpi/96));
            if(width<=0 || height<=0 || width>36000 || height>36000 || (long)width*height>800000000)
                throw new ArgumentException("Offline tiled preview exceeds its page dimension limit.");
            DrawingGroup clipped=new DrawingGroup {ClipGeometry=new RectangleGeometry(new Rect(size))};
            clipped.Children.Add(aliasedText?AliasedTextOutlines(drawing):drawing);
            int left=width,top=height,right=-1,bottom=-1;
            const int tile=1024;
            // Pass 1 locates visible engraving using bounded rasters. Never
            // allocate a 30x18-inch, 1200-DPI page bitmap (over 3 GB).
            for(int y=0;y<height;y+=tile)
            for(int x=0;x<width;x+=tile)
            {
                int w=Math.Min(tile,width-x),h=Math.Min(tile,height-y);
                BitmapSource part=RenderRegion(clipped,x,y,w,h,dpi);
                byte[] row=new byte[w*4];
                for(int py=0;py<h;py++)
                {
                    part.CopyPixels(new Int32Rect(0,py,w,1),row,row.Length,0);
                    for(int px=0;px<w;px++)
                    {
                        int i=px*4;
                        if(row[i]==255 && row[i+1]==255 && row[i+2]==255) continue;
                        left=Math.Min(left,x+px);right=Math.Max(right,x+px);
                        top=Math.Min(top,y+py);bottom=Math.Max(bottom,y+py);
                    }
                }
            }
            if(right<left) {originX=originY=0;return RenderRegion(clipped,0,0,1,1,dpi);}
            originX=left;originY=top;
            int cropWidth=right-left+1,cropHeight=bottom-top+1;
            if((long)cropWidth*cropHeight>MaxPixels)
                throw new ArgumentException("Engraving region exceeds the 50 megapixel limit; reduce artwork size or resolution.");
            // Pass 2 renders just that pixel-aligned region. Existing exposure
            // extraction keeps original page coordinates via the reported origin.
            return RenderRegion(clipped,left,top,cropWidth,cropHeight,dpi);
        }

        static BitmapSource RenderRegion(Drawing drawing,int x,int y,int width,int height,double dpi)
        {
            DrawingGroup shifted=new DrawingGroup {Transform=new TranslateTransform(-x*96.0/dpi,-y*96.0/dpi)};
            shifted.Children.Add(drawing);
            return Render(shifted,new Size(width*96.0/dpi,height*96.0/dpi),dpi,false,width,height);
        }

        static bool CorelClipsEngraving(Drawing drawing, Size size, CorelXpLayout layout, bool aliasedText)
        {
            // Include a pixel-aligned margin and the nominal-page fringe so a
            // compatibility mapping cannot silently crop engraving at an edge.
            const int pad = 10;
            int width = (int)Math.Ceiling(size.Width * layout.Dpi / 96) + pad*2;
            int height = (int)Math.Ceiling(size.Height * layout.Dpi / 96) + pad*2;
            DrawingGroup padded = new DrawingGroup { Transform = new TranslateTransform(pad*96.0/layout.Dpi, pad*96.0/layout.Dpi) };
            padded.Children.Add(drawing);
            BitmapSource bitmap = Render(padded, new Size(width*96.0/layout.Dpi, height*96.0/layout.Dpi), layout.Dpi, aliasedText, width, height);
            byte[] row = new byte[width*4];
            for (int y=0; y<height; y++)
            {
                bitmap.CopyPixels(new Int32Rect(0,y,width,1),row,row.Length,0);
                for (int x=0; x<width; x++)
                {
                    if (x>=pad && x<pad+layout.Width && y>=pad && y<pad+layout.Height) continue;
                    int i=x*4;
                    if (row[i]<255 || row[i+1]<255 || row[i+2]<255) return true;
                }
            }
            return false;
        }

        static string N(double value) { return value.ToString("0.######", CultureInfo.InvariantCulture); }
        static void WriteSvg(string path, PageReport report)
        {
            StringBuilder svg = new StringBuilder();
            svg.AppendFormat(CultureInfo.InvariantCulture,
                "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{0}mm\" height=\"{1}mm\" viewBox=\"0 0 {0} {1}\">\n<title>Offline cutting preview in millimeters</title>\n", N(report.width_mm), N(report.height_mm));
            svg.Append("<g fill=\"none\" stroke=\"red\" stroke-width=\"0.1\">\n");
            foreach (CutPath cut in report.cuts)
            {
                svg.Append(cut.closed ? "<polygon points=\"" : "<polyline points=\"");
                foreach (double[] point in cut.points_mm) svg.Append(N(point[0]) + "," + N(point[1]) + " ");
                svg.Append("\"/>\n");
            }
            svg.Append("</g>\n</svg>\n");
            using (StreamWriter writer = new StreamWriter(new FileStream(path, FileMode.CreateNew), new UTF8Encoding(false))) writer.Write(svg);
        }

        public static IntakeReport Read(string source, string destination, Options options)
        {
            options.Validate();
            source = Path.GetFullPath(source);
            destination = Path.GetFullPath(destination);
            if (Directory.Exists(destination) || File.Exists(destination)) throw new IOException("Output path already exists; choose a new directory.");
            Directory.CreateDirectory(destination);
            // Snapshot before parsing. The report hashes the actual bytes parsed.
            string snapshot = Path.Combine(destination, "source.bin");
            using (FileStream input = File.OpenRead(source))
            {
                if (input.Length == 0 || input.Length > 64 * 1024 * 1024) throw new ArgumentException("XPS input must be nonempty and at most 64 MiB.");
                using (FileStream output = new FileStream(snapshot, FileMode.CreateNew)) input.CopyTo(output);
            }
            IntakeReport report = new IntakeReport { dpi = options.Dpi, cut_color = options.AnyCutColor ? "any" : options.CutColor.HasValue ? options.CutColor.Value.ToString() : null,
                schema_version = options.ColorReview ? 3 : 2,
                status = options.ColorReview ? "offline_color_review_only" : "offline_preview_only",
                render_dpi = options.RenderDpi, raster_grid = options.RasterGrid,
                text_rendering = options.AliasedText ? "outline-aliased" : "auto", tiled_raster=options.TiledRaster, cut_paths_only=options.CutPathsOnly,
                max_cut_width_mm = options.MaxCutWidthMm, flatten_tolerance_mm = options.FlattenToleranceMm };
            using (SHA256 hash = SHA256.Create())
            using (FileStream file = File.OpenRead(snapshot)) report.source_sha256 = BitConverter.ToString(hash.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
            string renderSource = snapshot;
            if (options.CorelXpGrid)
            {
                options.CorelLayout = new CorelXpLayout(options.Dpi, CorelXpLayout.ReadSourceDpi(snapshot));
                report.corel_xp_compatibility = new CorelXpReport { source_printer_dpi = options.CorelLayout.SourceDpi, target_dpi = options.Dpi };
            }
            if (NativeXps.Convert(snapshot, null, NativeXps.MicrosoftXps) == NativeXps.OpenXps)
            {
                report.source_format = "OpenXPS";
                report.normalized_file = "normalized.xps";
                renderSource = Path.Combine(destination, report.normalized_file);
                NativeXps.Convert(snapshot, renderSource, NativeXps.MicrosoftXps);
            }
            using (XpsDocument document = new XpsDocument(renderSource, FileAccess.Read))
            {
                FixedDocumentSequence sequence = document.GetFixedDocumentSequence();
                if (sequence == null) throw new NotSupportedException("The Windows XPS reader could not load this document.");
                DocumentPaginator pages = sequence.DocumentPaginator;
                pages.ComputePageCount();
                if (!pages.IsPageCountValid || pages.PageCount < 1 || pages.PageCount > 100)
                    throw new ArgumentException("Document must contain between 1 and 100 pages.");
                for (int i = 0; i < pages.PageCount; i++)
                {
                    using (DocumentPage page = pages.GetPage(i)) report.pages.Add(ProcessPage(page.Visual, page.Size, i + 1, destination, options));
                }
            }
            // A manifest is published only after every page succeeds. Incomplete
            // directories are diagnostic evidence, never queue-ready documents.
            string json = new JavaScriptSerializer { MaxJsonLength = 64 * 1024 * 1024 }.Serialize(report);
            using (StreamWriter writer = new StreamWriter(new FileStream(Path.Combine(destination, "document.json"), FileMode.CreateNew), new UTF8Encoding(false))) writer.Write(json);
            return report;
        }
    }

    public static class Program
    {
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if (args.Length < 2) throw new ArgumentException("Usage: Aurora.XpsIntake.exe SOURCE.xps NEW-OUTPUT-DIRECTORY [--dpi 167] [--tiled-raster on|off] [--color-review on|off] [--raster-grid document-dpi|aurora-167-6mil-draft|xp-167-6mil-draft|coreldraw-xp-draft] [--text-rendering auto|outline-aliased] [--cut-color #RRGGBB] [--max-cut-width-mm 0.1] [--curve-tolerance-mm 0.01]");
                Options options = new Options();
                for (int i = 2; i < args.Length; i += 2)
                {
                    if (i + 1 >= args.Length) throw new ArgumentException("Missing option value.");
                    switch (args[i])
                    {
                        case "--dpi": options.Dpi = Int32.Parse(args[i + 1], CultureInfo.InvariantCulture); break;
                        case "--tiled-raster":
                            if(args[i+1]!="on" && args[i+1]!="off") throw new ArgumentException("Use on or off for tiled rendering.");
                            options.TiledRaster=args[i+1]=="on";break;
                        case "--color-review":
                            if(args[i+1]!="on" && args[i+1]!="off") throw new ArgumentException("Use on or off for color review.");
                            options.ColorReview=args[i+1]=="on";break;
                        case "--raster-grid":
                            if (args[i + 1] != "document-dpi" && args[i + 1] != "aurora-167-6mil-draft" && args[i + 1] != "xp-167-6mil-draft" && args[i + 1] != "coreldraw-xp-draft") throw new ArgumentException("Unsupported raster grid.");
                            options.AuroraGrid = args[i + 1] == "aurora-167-6mil-draft";
                            options.XpGrid = args[i + 1] == "xp-167-6mil-draft";
                            options.CorelXpGrid = args[i + 1] == "coreldraw-xp-draft"; break;
                        case "--text-rendering":
                            if (args[i + 1] != "auto" && args[i + 1] != "outline-aliased") throw new ArgumentException("Unsupported text rendering mode.");
                            options.AliasedText = args[i + 1] == "outline-aliased"; break;
                        case "--cut-color":
                            options.AnyCutColor=args[i+1]=="any";
                            options.CutColor=options.AnyCutColor ? (Color?)null : (Color)ColorConverter.ConvertFromString(args[i+1]);break;
                        case "--cut-paths-only":
                            if(args[i+1]!="on" && args[i+1]!="off") throw new ArgumentException("Use on or off for cut-path-only review.");
                            options.CutPathsOnly=args[i+1]=="on";break;
                        case "--max-cut-width-mm": options.MaxCutWidthMm = Double.Parse(args[i + 1], CultureInfo.InvariantCulture); break;
                        case "--curve-tolerance-mm": options.FlattenToleranceMm = Double.Parse(args[i + 1], CultureInfo.InvariantCulture); break;
                        default: throw new ArgumentException("Unknown option: " + args[i]);
                    }
                }
                IntakeReport report = Intake.Read(args[0], args[1], options);
                Console.WriteLine("Prepared offline previews for {0} page(s): {1}", report.pages.Count, Path.GetFullPath(args[1]));
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
        }
    }
}
