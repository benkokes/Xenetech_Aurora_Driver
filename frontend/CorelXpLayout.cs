// Explicit experimental fit to the CorelDRAW X7 / XP 11 reference captures.
using System;
using System.IO;
using System.IO.Packaging;
using System.Xml;
using System.Windows;

namespace Aurora.Frontend
{
    public sealed class CorelXpReport
    {
        public string model = "coreldraw-x7-to-xp11-flatbed-v1";
        public string validation = "reference_fit_not_physical_calibration";
        public int source_printer_dpi, target_dpi;
    }

    internal sealed class CorelXpLayout
    {
        internal readonly int Dpi, SourceDpi;
        internal int Width { get { return Dpi == 167 ? 5000 : 3000; } }
        internal int Height { get { return Dpi == 167 ? 3000 : 1800; } }
        internal int CenterX { get { return Dpi == 167 ? 5 : 0; } }
        internal int CenterY { get { return Dpi == 167 ? 3 : 0; } }
        internal double ShiftX { get { return (1.0 / SourceDpi - (1.0 + CenterX) / Dpi) * 96; } }
        internal double ShiftY { get { return (1.0 / SourceDpi - (1.0 + CenterY) / Dpi) * 96; } }
        internal CorelXpLayout(int dpi, int sourceDpi)
        {
            if ((dpi != 100 && dpi != 167) || sourceDpi != 600)
                throw new ArgumentException("The Corel XP reference profile requires target 100/167 DPI and a measured 600-DPI source ticket.");
            Dpi = dpi; SourceDpi = sourceDpi;
        }
        internal void CheckPage(Size size)
        {
            if (Math.Abs(size.Width - 2880) > 0.000001 || Math.Abs(size.Height - 1728) > 0.000001)
                throw new ArgumentException("The Corel XP reference profile is limited to a 30 x 18 inch page.");
        }
        internal static int ReadSourceDpi(string source)
        {
            const string psf = "http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework";
            const string psk = "http://schemas.microsoft.com/windows/2003/08/printing/printschemakeywords";
            int result = 0;
            using (Package package = Package.Open(source, FileMode.Open, FileAccess.Read))
            foreach (PackagePart part in package.GetParts())
            {
                if (part.ContentType != "application/vnd.ms-printing.printticket+xml") continue;
                using (Stream stream = part.GetStream(FileMode.Open, FileAccess.Read))
                using (XmlReader reader = XmlReader.Create(stream, new XmlReaderSettings {
                    DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null, MaxCharactersInDocument = 1024 * 1024 }))
                {
                    XmlDocument xml = new XmlDocument { XmlResolver = null }; xml.Load(reader);
                    foreach (XmlElement feature in xml.GetElementsByTagName("Feature", psf))
                    {
                        if (!Keyword(feature, "PageResolution", psk)) continue;
                        int x = 0, y = 0;
                        foreach (XmlElement prop in feature.GetElementsByTagName("ScoredProperty", psf))
                        {
                            XmlNodeList values = prop.GetElementsByTagName("Value", psf);
                            int value;
                            if (values.Count != 1 || !Int32.TryParse(values[0].InnerText, out value))
                                throw new ArgumentException("Invalid source printer resolution ticket.");
                            if (Keyword(prop, "ResolutionX", psk)) x = value;
                            if (Keyword(prop, "ResolutionY", psk)) y = value;
                        }
                        if (x != 600 || y != 600 || (result != 0 && result != x))
                            throw new ArgumentException("Source ticket is not uniformly 600 DPI; Corel reference profile cannot be applied.");
                        result = x;
                    }
                }
            }
            if (result == 0) throw new ArgumentException("Source printer resolution is missing; Corel reference profile cannot be applied.");
            return result;
        }
        static bool Keyword(XmlElement element, string name, string ns)
        {
            string[] parts = element.GetAttribute("name").Split(':');
            return parts.Length == 2 && parts[1] == name && element.GetNamespaceOfPrefix(parts[0]) == ns;
        }
    }
}
