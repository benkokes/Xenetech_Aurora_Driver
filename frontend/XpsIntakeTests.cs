using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Xps.Packaging;

namespace Aurora.Frontend
{
    public static class IntakeTests
    {
        static int passed;
        static Options Cutting() { return new Options { Dpi = 96, CutColor = Colors.Red }; }
        static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
        static void Near(double actual, double expected, string message) { Check(Math.Abs(actual - expected) < 0.0001, message + ": " + actual + " != " + expected); }
        static GeometryDrawing Line(Brush brush, double width)
        {
            return new GeometryDrawing(null, new Pen(brush, width), new LineGeometry(new Point(10, 20), new Point(90, 20)));
        }
        static PageReport Split(Drawing drawing, Options options)
        {
            PageReport report = new PageReport();
            Intake.Separate(drawing, Matrix.Identity, new List<Geometry>(), true, report, options);
            return report;
        }
        static void Run(string name, Action action)
        {
            action(); passed++; Console.WriteLine("PASS " + name);
        }
        static byte[] Pixels(BitmapSource bitmap)
        {
            byte[] bytes = new byte[bitmap.PixelWidth * bitmap.PixelHeight * 4];
            bitmap.CopyPixels(bytes, bitmap.PixelWidth * 4, 0);
            return bytes;
        }
        static BitmapSource Image(string path)
        {
            BitmapImage image = new BitmapImage();
            image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad;
            image.UriSource = new Uri(Path.GetFullPath(path)); image.EndInit();
            return new FormatConvertedBitmap(image, PixelFormats.Pbgra32, null, 0);
        }
        static byte LayerPixel(SemanticColorReport report, string color, string directory, int x, int y)
        {
            foreach(SemanticColorLayer layer in report.layers)if(layer.color==color)
            {
                ExposureReport image=layer.coverage;
                if(x<image.x_pixels || y<image.y_pixels || x>=image.x_pixels+image.width || y>=image.y_pixels+image.height)return 0;
                return File.ReadAllBytes(Path.Combine(directory,image.file))[(y-image.y_pixels)*image.width+x-image.x_pixels];
            }
            return 0;
        }
        static void Fixture(string path)
        {
            FixedDocument document = new FixedDocument();
            for (int pageNumber = 0; pageNumber < 2; pageNumber++)
            {
                FixedPage page = new FixedPage { Width = 192, Height = 144 };
                Canvas canvas = new Canvas { RenderTransform = new TranslateTransform(8, 4) };
                System.Windows.Shapes.Path cut = new System.Windows.Shapes.Path {
                    Stroke = Brushes.Red, StrokeThickness = 0.2,
                    Data = Geometry.Parse("M 16,16 L 112,16 112,64 16,64 Z") };
                canvas.Children.Add(cut);
                canvas.Children.Add(new System.Windows.Shapes.Path { Fill = Brushes.Black,
                    Data = Geometry.Parse("M 30,30 L 45,30 45,45 30,45 Z") });
                TextBlock text = new TextBlock { Text = "Aurora", FontSize = 14, Foreground = Brushes.Black };
                Canvas.SetLeft(text, 20); Canvas.SetTop(text, 80); canvas.Children.Add(text);
                byte[] pixels = { 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 255 };
                BitmapSource bitmap = BitmapSource.Create(2, 2, 96, 96, PixelFormats.Bgra32, null, pixels, 8);
                System.Windows.Controls.Image image = new System.Windows.Controls.Image { Source = bitmap, Width = 20, Height = 20 };
                Canvas.SetLeft(image, 140); Canvas.SetTop(image, 90); canvas.Children.Add(image);
                page.Children.Add(canvas);
                page.Measure(new Size(page.Width, page.Height)); page.Arrange(new Rect(0, 0, page.Width, page.Height)); page.UpdateLayout();
                PageContent content = new PageContent();
                ((System.Windows.Markup.IAddChild)content).AddChild(page);
                document.Pages.Add(content);
            }
            using (XpsDocument xps = new XpsDocument(path, FileAccess.ReadWrite)) XpsDocument.CreateXpsDocumentWriter(xps).Write(document);
        }

        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                string root = Path.Combine(Path.GetFullPath(args[0]), Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(root);
                Run("millimeter coordinates and stroke removal", delegate {
                    GeometryDrawing line = Line(Brushes.Red, 0.2);
                    PageReport result = Split(line, Cutting());
                    Check(result.cuts.Count == 1 && line.Pen == null, "Thin red line wasn't separated");
                    Near(result.cuts[0].points_mm[0][0], 10 * 25.4 / 96, "X coordinate");
                    Near(result.cuts[0].points_mm[1][1], 20 * 25.4 / 96, "Y coordinate");
                });
                Run("default preserves every stroke for engraving", delegate {
                    GeometryDrawing line = Line(Brushes.Red, 0.2);
                    Check(Split(line, new Options()).cuts.Count == 0 && line.Pen != null, "Default inferred a cut rule");
                });
                Run("stroke width and exact color classification", delegate {
                    Check(Split(Line(Brushes.Red, 1), Cutting()).cuts.Count == 0, "Wide red line cut");
                    Check(Split(Line(Brushes.Blue, 0.2), Cutting()).cuts.Count == 0, "Blue line cut");
                });
                Run("hairline cuts use width regardless of stroke color", delegate {
                    Options options=new Options {AnyCutColor=true,MaxCutWidthMm=0.5*25.4/96+0.000001};
                    foreach(Brush brush in new Brush[] {Brushes.Black,Brushes.Red,Brushes.Blue,Brushes.White})
                    {
                        Check(Split(Line(brush,0.5),options).cuts.Count==1,"Hairline color was excluded");
                        Check(Split(Line(brush,2.0/3),options).cuts.Count==0,"Half-point outline became a hairline cut");
                    }
                    GeometryDrawing fill=new GeometryDrawing(Brushes.Black,null,new RectangleGeometry(new Rect(10,10,20,20)));
                    Check(Split(fill,options).cuts.Count==0,"Filled artwork became cutting outlines");
                });
                Run("hairline classification accounts for scaling and rejects unsafe strokes", delegate {
                    Options options=new Options {AnyCutColor=true,MaxCutWidthMm=0.5*25.4/96+0.000001};
                    DrawingGroup scaled=new DrawingGroup {Transform=new ScaleTransform(2,2)};
                    scaled.Children.Add(Line(Brushes.Black,0.5));
                    Check(Split(scaled,options).cuts.Count==0,"Scaled thick stroke was cut");
                    SolidColorBrush translucent=new SolidColorBrush(Color.FromArgb(128,0,0,0));
                    PageReport report=Split(Line(translucent,0.5),options);
                    Check(report.cuts.Count==0 && report.review_reasons.Count==1,"Transparent hairline was silently cut");
                });
                Run("nested scale rotation and translation", delegate {
                    DrawingGroup child = new DrawingGroup { Transform = new ScaleTransform(2, 2) };
                    child.Children.Add(Line(Brushes.Red, 0.1));
                    Matrix transform = Matrix.Identity; transform.Rotate(90); transform.Translate(200, 10);
                    DrawingGroup parent = new DrawingGroup { Transform = new MatrixTransform(transform) }; parent.Children.Add(child);
                    PageReport result = Split(parent, Cutting());
                    double[] first = result.cuts[0].points_mm[0];
                    Near(first[0], 160 * 25.4 / 96, "Rotated X"); Near(first[1], 30 * 25.4 / 96, "Rotated Y");
                    Near(result.cuts[0].width_mm, 0.2 * 25.4 / 96, "Transformed stroke width");
                });
                Run("geometry transform is applied once", delegate {
                    GeometryDrawing line = Line(Brushes.Red, 0.2);
                    line.Geometry.Transform = new TranslateTransform(50, 60);
                    PageReport result = Split(line, Cutting());
                    Near(result.cuts[0].points_mm[0][0], 60 * 25.4 / 96, "Geometry X");
                    Near(result.cuts[0].points_mm[0][1], 80 * 25.4 / 96, "Geometry Y");
                });
                Run("mirrored geometry preserves its page position", delegate {
                    Matrix mirror = new Matrix(-1, 0, 0, 1, 100, 0);
                    DrawingGroup group = new DrawingGroup { Transform = new MatrixTransform(mirror) };
                    group.Children.Add(Line(Brushes.Red, 0.2));
                    PageReport result = Split(group, Cutting());
                    Near(result.cuts[0].points_mm[0][0], 90 * 25.4 / 96, "Mirrored start");
                    Near(result.cuts[0].points_mm[1][0], 10 * 25.4 / 96, "Mirrored end");
                });
                Run("nonuniform scale uses the maximum stroke width", delegate {
                    DrawingGroup group = new DrawingGroup { Transform = new ScaleTransform(1, 10) };
                    group.Children.Add(Line(Brushes.Red, 0.2));
                    Check(Split(group, Cutting()).cuts.Count == 0, "Scaled wide stroke cut");
                });
                Run("bezier is flattened in physical page units", delegate {
                    GeometryDrawing curve = new GeometryDrawing(null, new Pen(Brushes.Red, 0.1), Geometry.Parse("M 0,0 C 0,100 100,100 100,0"));
                    PageReport result = Split(curve, Cutting());
                    Check(result.cuts[0].points_mm.Count > 10, "Curve collapsed to a chord");
                    double maximumY = 0;
                    foreach (double[] point in result.cuts[0].points_mm) maximumY = Math.Max(maximumY, point[1]);
                    Near(maximumY, 75 * 25.4 / 96, "Bezier midpoint");
                });
                Run("clip containment and boundary-crossing review", delegate {
                    DrawingGroup contained = new DrawingGroup { ClipGeometry = new RectangleGeometry(new Rect(0, 0, 100, 100)) };
                    contained.Children.Add(Line(Brushes.Red, 0.2));
                    Check(Split(contained, Cutting()).cuts.Count == 1, "Contained clip rejected");
                    DrawingGroup clipped = new DrawingGroup { ClipGeometry = new RectangleGeometry(new Rect(0, 0, 50, 100)) };
                    GeometryDrawing line = Line(Brushes.Red, 0.2); clipped.Children.Add(line);
                    PageReport result = Split(clipped, Cutting());
                    Check(result.cuts.Count == 0 && result.review_reasons.Count == 1 && line.Pen != null, "Clipped stroke silently exported");
                });
                Run("transparency and dashes require review", delegate {
                    DrawingGroup transparent = new DrawingGroup { Opacity = 0.5 }; transparent.Children.Add(Line(Brushes.Red, 0.2));
                    PageReport result = Split(transparent, Cutting());
                    Check(result.cuts.Count == 0 && result.review_reasons.Count == 1, "Transparent cut exported");
                    GeometryDrawing dashed = Line(Brushes.Red, 0.2); dashed.Pen.DashStyle = DashStyles.Dash;
                    Check(Split(dashed, Cutting()).review_reasons.Count == 1, "Dashed cut not reported");
                });
                Run("fill stays after cut stroke removal", delegate {
                    GeometryDrawing shape = new GeometryDrawing(Brushes.Black, new Pen(Brushes.Red, 0.2), new RectangleGeometry(new Rect(10, 10, 30, 30)));
                    PageReport result = Split(shape, Cutting());
                    Check(result.cuts.Count == 1 && result.cuts[0].closed && shape.Brush == Brushes.Black && shape.Pen == null, "Fill was removed or path open");
                });
                Run("unstroked segment does not become a cutting bridge", delegate {
                    PathFigure figure = new PathFigure { StartPoint = new Point(10, 10) };
                    figure.Segments.Add(new LineSegment(new Point(20, 10), true));
                    figure.Segments.Add(new LineSegment(new Point(30, 10), false));
                    figure.Segments.Add(new LineSegment(new Point(40, 10), true));
                    GeometryDrawing shape = new GeometryDrawing(null, new Pen(Brushes.Red, 0.2), new PathGeometry(new PathFigure[] { figure }));
                    PageReport result = Split(shape, Cutting());
                    Check(result.cuts.Count == 2, "Cut paths bridged a gap");
                    Near(result.cuts[1].points_mm[0][0], 30 * 25.4 / 96, "Second subpath start");
                });
                Run("visual capture matches original pixels", delegate {
                    DrawingVisual child = new DrawingVisual(); child.Transform = new ScaleTransform(1.5, 1.5); child.Offset = new Vector(10, 5);
                    child.Opacity = 0.7; child.Clip = new RectangleGeometry(new Rect(0, 0, 45, 45));
                    using (DrawingContext dc = child.RenderOpen()) dc.DrawRectangle(Brushes.Black, null, new Rect(5, 5, 60, 60));
                    ContainerVisual parent = new ContainerVisual(); parent.Children.Add(child);
                    RenderTargetBitmap direct = new RenderTargetBitmap(120, 100, 96, 96, PixelFormats.Pbgra32); direct.Render(parent);
                    DrawingGroup captured = Intake.Capture(parent);
                    DrawingVisual reconstruction = new DrawingVisual(); using (DrawingContext dc = reconstruction.RenderOpen()) dc.DrawDrawing(captured);
                    RenderTargetBitmap rebuilt = new RenderTargetBitmap(120, 100, 96, 96, PixelFormats.Pbgra32); rebuilt.Render(reconstruction);
                    byte[] expected = Pixels(direct), actual = Pixels(rebuilt);
                    Check(expected.Length == actual.Length, "Size mismatch");
                    for (int i = 0; i < expected.Length; i++) Check(expected[i] == actual[i], "Visual reconstruction differs at byte " + i);
                });
                string source = Path.Combine(root, "fixture.xps");
                Run("real XPS round trip with paths glyphs images and two pages", delegate {
                    Fixture(source);
                    string output = Path.Combine(root, "separated");
                    IntakeReport report = Intake.Read(source, output, Cutting());
                    Check(report.pages.Count == 2 && report.source_sha256.Length == 64, "Document metadata incorrect");
                    foreach (PageReport page in report.pages)
                    {
                        Check(page.cuts.Count == 1 && page.cuts[0].closed && page.removed_cut_strokes == 1, "Round trip lost a cutting rectangle");
                        Check(page.glyph_drawings > 0 && page.image_drawings + page.image_brushes > 0, "Glyph/image drawing lost");
                        Near(page.width_mm, 50.8, "Page width"); Near(page.height_mm, 38.1, "Page height");
                        Near(page.cuts[0].points_mm[0][0], 24 * 25.4 / 96, "Cut placement X");
                        Near(page.cuts[0].points_mm[0][1], 20 * 25.4 / 96, "Cut placement Y");
                        Check(page.review_reasons.Count == 0, "Unexpected review reason");
                        BitmapSource bitmap = Image(Path.Combine(output, page.engraving_png));
                        byte[] pixels = Pixels(bitmap);
                        Check(pixels[(35 * bitmap.PixelWidth + 40) * 4] == 0, "Engraving fill missing");
                        Check(pixels[(20 * bitmap.PixelWidth + 60) * 4] == 255, "Cut stroke remained in engraving");
                        Check(pixels[(96 * bitmap.PixelWidth + 150) * 4] < 30, "Embedded image missing");
                    }
                    Check(File.Exists(Path.Combine(output, "document.json")), "Manifest not published");
                });
                Run("default 167 DPI rounds raster dimensions up", delegate {
                    IntakeReport result = Intake.Read(source, Path.Combine(root, "default-settings"), new Options());
                    Check(result.pages[0].pixel_width == 334 && result.pages[0].pixel_height == 251, "DPI conversion incorrect");
                    Check(result.pages[0].cuts.Count == 0, "Default extraction enabled");
                });
                Run("native OpenXPS conversion preserves page pixels and cutting paths", delegate {
                    string open = Path.Combine(root, "fixture.oxps");
                    NativeXps.Convert(source, open, NativeXps.OpenXps);
                    Check(NativeXps.Convert(open, null, NativeXps.MicrosoftXps) == NativeXps.OpenXps, "Native output is not OpenXPS");
                    string converted = Path.Combine(root, "openxps-output");
                    IntakeReport result = Intake.Read(open, converted, Cutting());
                    Check(result.source_format == "OpenXPS" && result.normalized_file == "normalized.xps", "Conversion provenance missing");
                    Check(result.pages.Count == 2 && result.pages[0].cuts.Count == 1, "Conversion lost pages or geometry");
                    byte[] original = Pixels(Image(Path.Combine(root, "separated", "page-001-engraving.png")));
                    byte[] actual = Pixels(Image(Path.Combine(converted, "page-001-engraving.png")));
                    Check(original.Length == actual.Length, "Converted dimensions changed");
                    for (int i = 0; i < original.Length; i++) Check(original[i] == actual[i], "Native conversion changed a rendered pixel at " + i);
                    Near(result.pages[0].cuts[0].points_mm[0][0], 6.35, "Converted cut location");
                    bool rejected = false;
                    try { NativeXps.Convert(source, open, NativeXps.OpenXps); } catch (IOException) { rejected = true; }
                    Check(rejected, "Native conversion overwrote existing output");
                });
                Run("invalid document never publishes a complete manifest", delegate {
                    string invalid = Path.Combine(root, "invalid.xps"), output = Path.Combine(root, "invalid-output");
                    File.WriteAllText(invalid, "This is not XPS");
                    bool rejected = false;
                    try { Intake.Read(invalid, output, Cutting()); } catch (Exception) { rejected = true; }
                    Check(rejected && !File.Exists(Path.Combine(output, "document.json")), "Invalid input published");
                    Check(File.Exists(Path.Combine(output, "source.bin")), "Failed source snapshot missing");
                });
                Run("blank captured page is flagged for review", delegate {
                    string directory = Path.Combine(root, "blank"); Directory.CreateDirectory(directory);
                    DrawingVisual blank = new DrawingVisual();
                    PageReport page = Intake.ProcessPage(blank, new Size(96, 96), 1, directory, Cutting());
                    Check(!page.has_visible_artwork && page.engraving_nonwhite_pixels == 0 && page.review_reasons.Count == 1, "Blank page accepted without review");
                    string roundedDirectory = Path.Combine(root, "blank-rounded"); Directory.CreateDirectory(roundedDirectory);
                    page = Intake.ProcessPage(blank, new Size(1056, 816), 1, roundedDirectory, new Options { Dpi = 167 });
                    Check(!page.has_visible_artwork && page.engraving_nonwhite_pixels == 0, "Fractional raster edge mislabeled as artwork");
                    DrawingVisual cutOnly = new DrawingVisual();
                    using (DrawingContext dc = cutOnly.RenderOpen()) dc.DrawRectangle(null, new Pen(Brushes.Red, 0.2), new Rect(10, 10, 50, 50));
                    string cutDirectory = Path.Combine(root, "cut-only"); Directory.CreateDirectory(cutDirectory);
                    page = Intake.ProcessPage(cutOnly, new Size(96, 96), 1, cutDirectory, Cutting());
                    Check(page.has_visible_artwork && page.engraving_nonwhite_pixels == 0 && page.cuts.Count == 1 && page.review_reasons.Count == 0, "Cut-only page incorrectly labeled blank");
                });
                Run("no overwrite and bounded raster size", delegate {
                    bool rejected = false;
                    try { Intake.Read(source, Path.Combine(root, "separated"), Cutting()); } catch (IOException) { rejected = true; }
                    Check(rejected, "Output overwritten");
                    rejected = false;
                    try { Intake.Render(new DrawingGroup(), new Size(10000, 10000), 96); } catch (ArgumentException) { rejected = true; }
                    Check(rejected, "Unbounded raster permitted");
                    rejected = false;
                    try { new Options { MaxCutWidthMm = Double.NaN }.Validate(); } catch (ArgumentException) { rejected = true; }
                    Check(rejected, "NaN accepted");
                });
                Run("six-unit Aurora raster grid uses its actual sampling rate", delegate {
                    Options options = new Options { AuroraGrid = true };
                    BitmapSource bitmap = Intake.Render(new DrawingGroup(), new Size(576, 288), options.RenderDpi);
                    Check(bitmap.PixelWidth == 1000 && bitmap.PixelHeight == 500, "Six-inch native grid differs from 1000 pixels");
                    Near(options.RenderDpi * 6, 1000, "Native grid rate");
                    bool rejected = false;
                    try { new Options { AuroraGrid = true, Dpi = 300 }.Validate(); } catch (ArgumentException) { rejected = true; }
                    Check(rejected, "Wrong nominal DPI accepted for native grid");
                });
                Run("exposure crop preserves white black gray and page offsets", delegate {
                    byte[] pixels = new byte[4 * 3 * 4];
                    for (int i = 0; i < pixels.Length; i++) pixels[i] = 255;
                    for (int c = 0; c < 3; c++) { pixels[(1 * 4 + 1) * 4 + c] = 0; pixels[(1 * 4 + 2) * 4 + c] = 128; }
                    BitmapSource bitmap = BitmapSource.Create(4, 3, 96, 96, PixelFormats.Pbgra32, null, pixels, 16);
                    string directory = Path.Combine(root, "exposure-check"); Directory.CreateDirectory(directory);
                    ExposureReport result = ExposureImage.Write(bitmap, directory, 1);
                    Check(result.x_pixels == 1 && result.y_pixels == 1 && result.width == 2 && result.height == 1 && result.colored_pixels == 0, "Exposure crop incorrect");
                    byte[] signal = File.ReadAllBytes(Path.Combine(directory, result.file));
                    Check(signal.Length == 2 && signal[0] == 255 && signal[1] == 127, "Exposure polarity or gray level incorrect");
                    Check(result.sha256.Length == 64, "Exposure digest missing");
                });
                Run("XP grid preserves nominal sampling and aliased text keeps gray artwork", delegate {
                    Options options = new Options { XpGrid = true, AliasedText = true };
                    options.Validate();
                    Check(options.RasterGrid == "xp-167-6mil-draft", "XP profile lost");
                    Near(options.RenderDpi, 167, "XP sample rate");
                    BitmapSource empty = Intake.Render(new DrawingGroup(), new Size(96, 96), options.RenderDpi);
                    Check(empty.PixelWidth == 167 && empty.PixelHeight == 167, "Nominal inch differs from 167 pixels");
                    DrawingVisual visual = new DrawingVisual();
                    using (DrawingContext dc = visual.RenderOpen())
                    {
                        FormattedText text = new FormattedText("TEST", System.Globalization.CultureInfo.InvariantCulture,
                            FlowDirection.LeftToRight, new Typeface("Arial"), 24, Brushes.Black, 1.0);
                        dc.DrawText(text, new Point(10, 10));
                        dc.DrawRectangle(new SolidColorBrush(Color.FromRgb(128,128,128)), null, new Rect(10,70,30,10));
                    }
                    byte[] pixels = Pixels(Intake.Render(Intake.Capture(visual), new Size(96,96), 167, true));
                    bool black = false;
                    for (int y=0; y<100; y++) for (int x=0; x<167; x++)
                    {
                        byte value = pixels[(y*167+x)*4];
                        Check(value == 0 || value == 255, "Aliased black text contains gray pixels");
                        black |= value == 0;
                    }
                    Check(black, "Text vanished");
                    Check(pixels[(130*167+30)*4] == 128, "Gray artwork was thresholded");
                    bool rejected = false;
                    try { new Options { XpGrid=true, AuroraGrid=true }.Validate(); } catch (ArgumentException) { rejected=true; }
                    Check(rejected, "Conflicting profiles accepted");
                });
                Run("Corel reference layout requires explicit source ticket and fixed bed", delegate {
                    string package = Path.Combine(root, "resolution-ticket.zip");
                    using (System.IO.Packaging.Package zip = System.IO.Packaging.Package.Open(package, FileMode.CreateNew))
                    {
                        System.IO.Packaging.PackagePart ticket = zip.CreatePart(new Uri("/ticket.xml", UriKind.Relative), "application/vnd.ms-printing.printticket+xml");
                        using (StreamWriter writer = new StreamWriter(ticket.GetStream())) writer.Write(
                            "<a:PrintTicket xmlns:a='http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework' xmlns:b='http://schemas.microsoft.com/windows/2003/08/printing/printschemakeywords'><a:Feature name='b:PageResolution'><a:Option><a:ScoredProperty name='b:ResolutionX'><a:Value>600</a:Value></a:ScoredProperty><a:ScoredProperty name='b:ResolutionY'><a:Value>600</a:Value></a:ScoredProperty></a:Option></a:Feature></a:PrintTicket>");
                    }
                    Check(CorelXpLayout.ReadSourceDpi(package) == 600, "Source ticket resolution not measured");
                    CorelXpLayout layout = new CorelXpLayout(167,600);
                    Check(layout.Width == 5000 && layout.Height == 3000, "XP surface mismatch");
                    Near(layout.ShiftX * 167 / 96, 167.0/600-6, "Corel raster X shift");
                    Near(layout.ShiftY * 167 / 96, 167.0/600-4, "Corel raster Y shift");
                    layout.CheckPage(new Size(2880,1728));
                    bool rejected=false;
                    try { layout.CheckPage(new Size(192,144)); } catch (ArgumentException) { rejected=true; }
                    Check(rejected, "Different bed accepted for reference fit");
                    rejected=false;
                    try { new CorelXpLayout(167,1200); } catch (ArgumentException) { rejected=true; }
                    Check(rejected, "Different source DPI accepted");
                    layout = new CorelXpLayout(100,600);
                    Check(layout.Width == 3000 && layout.Height == 1800, "100 DPI surface mismatch");
                });
                Run("Corel placement flags engraving that would cross the legacy surface edge", delegate {
                    DrawingVisual visual = new DrawingVisual();
                    using (DrawingContext dc=visual.RenderOpen()) dc.DrawRectangle(Brushes.Black,null,new Rect(0,100,10,10));
                    Options options = new Options { CorelXpGrid=true, Dpi=100, CorelLayout=new CorelXpLayout(100,600) };
                    string directory=Path.Combine(root,"corel-edge"); Directory.CreateDirectory(directory);
                    PageReport page=Intake.ProcessPage(visual,new Size(2880,1728),1,directory,options);
                    Check(page.review_reasons.Count==1 && page.review_reasons[0].Contains("clip engraving"), "Engraving was silently cropped");
                });
                Run("tiled preview preserves full-render samples and page coordinates", delegate {
                    foreach(int dpi in new int[]{50,167,500})
                    {
                        Size size=new Size(1152,144);
                        double x=Math.Min(1020,12*dpi/2)*96.0/dpi;
                        DrawingVisual visual=new DrawingVisual();
                        using(DrawingContext dc=visual.RenderOpen())
                        {
                            dc.DrawRectangle(new SolidColorBrush(Color.FromRgb(128,128,128)),null,new Rect(x,20,35,28));
                            dc.DrawLine(new Pen(Brushes.Black,0.75),new Point(x-4,18),new Point(x+42,51));
                            dc.DrawRectangle(Brushes.Black,null,new Rect(-100,-100,5,5));
                        }
                        Drawing drawing=Intake.Capture(visual);
                        BitmapSource full=Intake.Render(drawing,size,dpi);
                        int ox,oy;BitmapSource tiled=Intake.RenderTiled(drawing,size,dpi,false,out ox,out oy);
                        string a=Path.Combine(root,"tile-full-"+dpi),b=Path.Combine(root,"tile-crop-"+dpi);
                        Directory.CreateDirectory(a);Directory.CreateDirectory(b);
                        ExposureReport fa=ExposureImage.Write(full,a,1),fb=ExposureImage.Write(tiled,b,1);
                        Check(fa.sha256==fb.sha256 && fa.width==fb.width && fa.height==fb.height,"Tiled raster samples changed at DPI "+dpi);
                        Check(fa.x_pixels==fb.x_pixels+ox && fa.y_pixels==fb.y_pixels+oy,"Tiled raster origin changed at DPI "+dpi);
                    }
                });
                Run("full bed 1200 DPI preview uses a bounded region and keeps cuts", delegate {
                    new Options {Dpi=50,TiledRaster=true}.Validate();
                    Options options=new Options {Dpi=1200,TiledRaster=true,CutColor=Colors.Red};options.Validate();
                    DrawingVisual visual=new DrawingVisual();
                    using(DrawingContext dc=visual.RenderOpen())
                    {
                        dc.DrawRectangle(Brushes.Black,null,new Rect(96,96,12,8));
                        dc.DrawRectangle(null,new Pen(Brushes.Red,0.2),new Rect(120,120,96,96));
                    }
                    string directory=Path.Combine(root,"tiled-1200");Directory.CreateDirectory(directory);
                    PageReport page=Intake.ProcessPage(visual,new Size(2880,1728),1,directory,options);
                    Check(page.pixel_width==36000 && page.pixel_height==21600,"High DPI logical bed changed");
                    Check(page.exposure!=null && page.exposure.width==150 && page.exposure.height==100,"High DPI crop dimensions differ");
                    Check(page.exposure.x_pixels==1200 && page.exposure.y_pixels==1200 && page.preview_x_pixels==1200,"High DPI page origin lost");
                    Check(page.cuts.Count==1 && page.removed_cut_strokes==1,"Tiled rendering lost vector separation");
                    bool rejected=false;
                    try { new Options {CorelXpGrid=true,TiledRaster=true}.Validate(); } catch(ArgumentException) {rejected=true;}
                    Check(rejected,"Offline tiled preview entered the live Corel profile");
                });
                Run("tiled preview rejects an oversized engraving region", delegate {
                    int x,y;bool rejected=false;
                    Drawing drawing=new GeometryDrawing(Brushes.Black,null,new RectangleGeometry(new Rect(0,0,8000,8000)));
                    try {Intake.RenderTiled(drawing,new Size(8000,8000),96,false,out x,out y);} catch(ArgumentException) {rejected=true;}
                    Check(rejected,"Oversized tiled exposure region was allowed");
                });
                Run("color review extracts all thin opaque colors while default remains exact red", delegate {
                    Options options = new Options {Dpi=167,CorelXpGrid=true,ColorReview=true};options.Validate();
                    DrawingGroup drawing = new DrawingGroup();
                    drawing.Children.Add(Line(Brushes.Blue,0.2));
                    drawing.Children.Add(Line(Brushes.Red,0.2));
                    drawing.Children.Add(Line(Brushes.Orange,0.2));
                    drawing.Children.Add(Line(Brushes.Blue,1));
                    PageReport result = Split(drawing,options);
                    Check(result.cuts.Count==3 && result.removed_cut_strokes==3,"Color review did not retain each cut color");
                    Check(result.cuts[0].color==Colors.Blue.ToString() && result.cuts[2].color==Colors.Orange.ToString(),"Cut RGB/order lost");
                    Check(Split(Line(Brushes.Blue,0.2),Cutting()).cuts.Count==0,"Ordinary red-only rule changed");
                    GeometryDrawing transparent=Line(new SolidColorBrush(Color.FromArgb(128,0,0,255)),0.2);
                    Check(Split(transparent,options).review_reasons.Count>0 && transparent.Pen!=null,"Transparent color cut was accepted");
                });
                Run("color RGB review preserves channels, black and nonwhite coverage", delegate {
                    string directory=Path.Combine(root,"rgb-review");Directory.CreateDirectory(directory);
                    byte[] pixels={255,255,255,255, 0,0,255,255, 255,0,0,255, 0,0,0,255, 255,255,255,255};
                    BitmapSource bitmap=BitmapSource.Create(5,1,167,167,PixelFormats.Pbgra32,null,pixels,20);
                    ColorReviewReport report=ColorReviewImage.Write(bitmap,directory,1);
                    Check(report.x_pixels==1 && report.width==3 && report.height==1 && report.nonwhite_pixels==3,"RGB crop wrong");
                    byte[] rgb=File.ReadAllBytes(Path.Combine(directory,report.file));
                    Check(BitConverter.ToString(rgb)=="FF-00-00-00-00-FF-00-00-00","BGRA/RGB conversion lost color channels or black");
                    Check(BitConverter.ToString(File.ReadAllBytes(Path.Combine(directory,report.coverage_file)))=="FF-FF-FF","Coverage differs");
                    Check(report.sha256.Length==64 && report.coverage_sha256.Length==64,"RGB/coverage hashes absent");
                    bool rejected=false;try {ColorReviewImage.Write(bitmap,directory,1);} catch(IOException) {rejected=true;}
                    Check(rejected,"RGB artifacts were overwritten");
                });
                Run("color review rejects unsupported configurations and transparent composites", delegate {
                    Options[] cases={new Options {ColorReview=true},new Options {ColorReview=true,CorelXpGrid=true,Dpi=100},
                        new Options {ColorReview=true,CorelXpGrid=true,CutColor=Colors.Red}};
                    foreach(Options option in cases) {bool rejected=false;try {option.Validate();} catch(ArgumentException) {rejected=true;}
                        Check(rejected,"Unverified color review configuration accepted");}
                    string directory=Path.Combine(root,"rgb-invalid");Directory.CreateDirectory(directory);
                    BitmapSource clear=BitmapSource.Create(1,1,167,167,PixelFormats.Pbgra32,null,new byte[] {0,0,0,128},4);
                    bool invalid=false;try {ColorReviewImage.Write(clear,directory,1);} catch(InvalidOperationException) {invalid=true;}
                    Check(invalid,"Partial alpha composite accepted");
                    BitmapSource white=BitmapSource.Create(1,1,167,167,PixelFormats.Pbgra32,null,new byte[] {255,255,255,255},4);
                    Check(ColorReviewImage.Write(white,directory,1)==null,"White background became colored artwork");
                });
                Run("color review page records explicit coverage limitation", delegate {
                    DrawingVisual visual=new DrawingVisual();
                    using(DrawingContext dc=visual.RenderOpen()) {dc.DrawRectangle(Brushes.Blue,null,new Rect(96,96,12,12));}
                    Options option=new Options {Dpi=167,CorelXpGrid=true,ColorReview=true,CorelLayout=new CorelXpLayout(167,600)};
                    string directory=Path.Combine(root,"rgb-page");Directory.CreateDirectory(directory);
                    PageReport result=Intake.ProcessPage(visual,new Size(2880,1728),1,directory,option);
                    Check(result.color_raster_review!=null && result.color_raster_review.coverage_limitation.Contains("White artwork"),"Coverage ambiguity hidden");
                    Check(result.review_reasons.Count>0,"Color review entered ordinary output without a hold");
                });
                Run("semantic layers preserve brush identity and fractional edge coverage", delegate {
                    DrawingGroup drawing=new DrawingGroup();
                    drawing.Children.Add(new GeometryDrawing(Brushes.Blue,null,new RectangleGeometry(new Rect(2.2,2.2,10,8))));
                    drawing.Children.Add(new GeometryDrawing(Brushes.Red,null,new RectangleGeometry(new Rect(18.2,2.2,10,8))));
                    string directory=Path.Combine(root,"semantic-edges");Directory.CreateDirectory(directory);
                    SemanticColorReport report=SemanticColorLayers.Write(drawing,new Size(40,20),167,false,70,35,directory,1);
                    Check(report.status=="prepared_offline_flat_color_layers" && report.layers.Count==2,"Semantic colors lost");
                    Check(report.layers[0].color=="#FFFF0000" && report.layers[1].color=="#FF0000FF","Palette identity/order differs");
                    foreach(SemanticColorLayer layer in report.layers)
                    {
                        bool fractional=false;foreach(byte value in File.ReadAllBytes(Path.Combine(directory,layer.coverage.file)))
                            if(value>0 && value<255)fractional=true;
                        Check(fractional,"Antialiased edge coverage was thresholded away");
                        Check(layer.coverage.colored_pixels==0,"Coverage layer contains colored samples");
                    }
                });
                Run("semantic masks retain colored and white occlusion", delegate {
                    DrawingGroup drawing=new DrawingGroup();
                    drawing.Children.Add(new GeometryDrawing(Brushes.Blue,null,new RectangleGeometry(new Rect(2,2,12,10))));
                    drawing.Children.Add(new GeometryDrawing(Brushes.Red,null,new RectangleGeometry(new Rect(8,2,12,10))));
                    drawing.Children.Add(new GeometryDrawing(Brushes.White,null,new RectangleGeometry(new Rect(4,4,2,2))));
                    string directory=Path.Combine(root,"semantic-occlusion");Directory.CreateDirectory(directory);
                    SemanticColorReport report=SemanticColorLayers.Write(drawing,new Size(24,16),96,false,24,16,directory,1);
                    Check(report.white_paint_excluded && report.layers.Count==2,"White paint became a palette pass");
                    Check(LayerPixel(report,"#FF0000FF",directory,10,5)==0,"Hidden blue appeared under red");
                    Check(LayerPixel(report,"#FFFF0000",directory,10,5)==255,"Foreground red disappeared");
                    Check(LayerPixel(report,"#FF0000FF",directory,4,4)==0,"White hole exposed underlying blue");
                    Check(LayerPixel(report,"#FF0000FF",directory,3,3)==255,"Visible blue removed");
                });
                Run("semantic layers preserve transforms clips and original drawing", delegate {
                    DrawingGroup drawing=new DrawingGroup {Transform=new TranslateTransform(5,7),ClipGeometry=new RectangleGeometry(new Rect(0,0,6,8))};
                    drawing.Children.Add(new GeometryDrawing(Brushes.Blue,null,new RectangleGeometry(new Rect(0,0,12,12))));
                    byte[] before=Pixels(Intake.Render(drawing,new Size(24,24),96));
                    string directory=Path.Combine(root,"semantic-transform");Directory.CreateDirectory(directory);
                    SemanticColorReport report=SemanticColorLayers.Write(drawing,new Size(24,24),96,false,24,24,directory,1);
                    Check(report.layers.Count==1 && report.layers[0].coverage.x_pixels==5 && report.layers[0].coverage.y_pixels==7,"Layer transform lost");
                    Check(report.layers[0].coverage.width==6 && report.layers[0].coverage.height==8,"Layer clip lost");
                    Check(BitConverter.ToString(before)==BitConverter.ToString(Pixels(Intake.Render(drawing,new Size(24,24),96))),"Layer rendering mutated source drawing");
                });
                Run("unsupported semantic color sources hold before rendering layers", delegate {
                    Drawing[] cases={
                        new GeometryDrawing(new LinearGradientBrush(Colors.Red,Colors.Blue,0),null,new RectangleGeometry(new Rect(0,0,8,8))),
                        new GeometryDrawing(new SolidColorBrush(Color.FromArgb(128,0,0,255)),null,new RectangleGeometry(new Rect(0,0,8,8))),
                        new DrawingGroup {Opacity=0.5},
                        new ImageDrawing(BitmapSource.Create(1,1,96,96,PixelFormats.Bgra32,null,new byte[]{0,0,0,255},4),new Rect(0,0,8,8))};
                    string directory=Path.Combine(root,"semantic-unsupported");Directory.CreateDirectory(directory);
                    foreach(Drawing drawing in cases)
                    {
                        SemanticColorReport report=SemanticColorLayers.Write(drawing,new Size(8,8),96,false,8,8,directory,1);
                        Check(report.status=="unsupported_flat_color_layers" && report.layers.Count==0 && report.unsupported_reason!=null,"Unsupported source silently classified");
                    }
                    Check(Directory.GetFiles(directory).Length==0,"Unsupported sources published coverage artifacts");
                });
                Run("semantic layers retain unmatched brush identity for explicit omission", delegate {
                    DrawingGroup drawing=new DrawingGroup();
                    drawing.Children.Add(new GeometryDrawing(new SolidColorBrush(Color.FromRgb(255,128,0)),null,new RectangleGeometry(new Rect(2,2,4,4))));
                    string directory=Path.Combine(root,"semantic-unknown");Directory.CreateDirectory(directory);
                    SemanticColorReport report=SemanticColorLayers.Write(drawing,new Size(8,8),96,false,8,8,directory,1);
                    Check(report.layers.Count==1 && report.layers[0].palette_index==-1 && report.layers[0].color=="#FFFF8000","Unknown color was reassigned to nearest palette entry");
                });
                Console.WriteLine("{0} frontend tests passed. Artifacts: {1}", passed, root);
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
