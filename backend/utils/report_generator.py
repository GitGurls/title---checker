import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import base64
import logging

logger = logging.getLogger(__name__)

class SAR_ReportGenerator:
    """Generate comprehensive SAR mission reports in PDF and other formats"""
    
    def __init__(self, output_dir: str = "exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.darkblue,
            alignment=1  # Center alignment
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkred,
            borderWidth=1,
            borderColor=colors.gray,
            borderPadding=5
        ))
    
    async def generate_pdf_report(
        self,
        export_id: str,
        simulation_data: Dict[str, Any],
        request_params: Dict[str, Any]
    ) -> str:
        """Generate comprehensive PDF mission report"""
        
        try:
            filename = f"SAR_Report_{export_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            
            # Title
            title = request_params.get('title', 'SAR Aircraft Disappearance Analysis Report')
            story.append(Paragraph(title, self.styles['CustomTitle']))
            story.append(Spacer(1, 20))
            
            # Mission Information
            story.extend(self._create_mission_info_section(request_params, simulation_data))
            
            # Executive Summary
            story.extend(self._create_executive_summary(simulation_data))
            
            # Simulation Parameters
            story.extend(self._create_simulation_parameters(simulation_data))
            
            # Results Analysis
            story.extend(self._create_results_analysis(simulation_data))
            
            # Search Zone Details
            story.extend(self._create_search_zone_details(simulation_data))
            
            # Recommendations
            story.extend(self._create_recommendations(simulation_data))
            
            # Map visualization (if requested)
            if request_params.get('include_map', True):
                story.extend(self._create_map_section(simulation_data))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            raise
    
    def _create_mission_info_section(self, request_params: Dict[str, Any], simulation_data: Dict[str, Any]) -> list:
        """Create mission information section"""
        story = []
        
        story.append(Paragraph("Mission Information", self.styles['SectionHeader']))
        
        mission_data = [
            ['Mission ID', request_params.get('mission_id', 'N/A')],
            ['Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')],
            ['Simulation ID', simulation_data.get('simulation_id', 'N/A')],
            ['Report Type', 'Aircraft Disappearance Probability Analysis'],
            ['Confidence Level', '95%'],
            ['Data Sources', 'Monte Carlo Simulation, Wind Drift Model, Bayesian Analysis']
        ]
        
        table = Table(mission_data, colWidths=[2*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_executive_summary(self, simulation_data: Dict[str, Any]) -> list:
        """Create executive summary section"""
        story = []
        
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        # Extract key metrics
        geojson = simulation_data.get('geojson', {})
        properties = geojson.get('properties', {})
        
        total_zones = properties.get('total_zones', 0)
        max_probability = properties.get('max_probability', 0)
        total_area = properties.get('total_area_km2', 0)
        
        summary_text = f"""
        This report presents the results of a comprehensive aircraft disappearance probability analysis 
        conducted using advanced Monte Carlo simulation, wind drift modeling, and Bayesian inference techniques.
        <br/><br/>
        <b>Key Findings:</b><br/>
        • {total_zones} probability zones identified<br/>
        • Maximum probability concentration: {max_probability:.1%}<br/>
        • Total search area: {total_area:,.1f} km²<br/>
        • Analysis incorporates wind drift, fuel consumption, and position uncertainty<br/>
        <br/>
        The analysis provides search and rescue teams with prioritized zones for deployment 
        of assets and resources to maximize the probability of successful recovery operations.
        """
        
        story.append(Paragraph(summary_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_simulation_parameters(self, simulation_data: Dict[str, Any]) -> list:
        """Create simulation parameters section"""
        story = []
        
        story.append(Paragraph("Simulation Parameters", self.styles['SectionHeader']))
        
        # Extract parameters from simulation data
        params = simulation_data.get('parameters_used', {})
        
        if params:
            param_data = [
                ['Parameter', 'Value', 'Unit'],
                ['Last Known Latitude', f"{params.get('lat', 'N/A'):.4f}", 'degrees'],
                ['Last Known Longitude', f"{params.get('lon', 'N/A'):.4f}", 'degrees'],
                ['Altitude', f"{params.get('altitude', 'N/A'):,}", 'feet'],
                ['Ground Speed', f"{params.get('speed', 'N/A')}", 'knots'],
                ['Heading', f"{params.get('heading', 'N/A')}", 'degrees'],
                ['Remaining Fuel', f"{params.get('fuel', 'N/A'):,}", 'liters'],
                ['Time Since Contact', f"{params.get('time_since_contact', 'N/A'):,}", 'seconds'],
                ['Wind Speed', f"{params.get('wind', {}).get('speed', 'N/A')}", 'knots'],
                ['Wind Direction', f"{params.get('wind', {}).get('direction', 'N/A')}", 'degrees']
            ]
        else:
            param_data = [['Parameter', 'Value', 'Unit'], ['No parameters available', '', '']]
        
        table = Table(param_data, colWidths=[2*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_results_analysis(self, simulation_data: Dict[str, Any]) -> list:
        """Create results analysis section"""
        story = []
        
        story.append(Paragraph("Analysis Results", self.styles['SectionHeader']))
        
        # Extract zone information
        geojson = simulation_data.get('geojson', {})
        features = geojson.get('features', [])
        
        if features:
            analysis_text = f"""
            The simulation identified {len(features)} distinct probability zones based on the 
            aircraft's last known position, flight parameters, and environmental conditions.
            <br/><br/>
            <b>Zone Prioritization:</b><br/>
            Zones are ranked by probability with the highest priority areas representing 
            the most likely crash locations based on:
            <br/>
            • Monte Carlo flight path simulation ({2000} iterations)<br/>
            • Wind drift modeling with altitude-dependent effects<br/>
            • Fuel consumption and endurance calculations<br/>
            • Position uncertainty based on last contact<br/>
            """
        else:
            analysis_text = "No probability zones were generated from the simulation."
        
        story.append(Paragraph(analysis_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_search_zone_details(self, simulation_data: Dict[str, Any]) -> list:
        """Create detailed search zone information"""
        story = []
        
        story.append(Paragraph("Search Zone Details", self.styles['SectionHeader']))
        
        geojson = simulation_data.get('geojson', {})
        features = geojson.get('features', [])
        
        if features:
            # Create zone summary table
            zone_data = [['Zone', 'Probability', 'Area (km²)', 'Risk Level', 'Priority']]
            
            for i, feature in enumerate(features[:10]):  # Limit to top 10 zones
                props = feature.get('properties', {})
                zone_data.append([
                    f"Zone {i+1}",
                    f"{props.get('probability', 0):.1%}",
                    f"{props.get('area_km2', 0):.1f}",
                    props.get('risk_level', 'Unknown').title(),
                    props.get('zone_rank', i+1)
                ])
            
            table = Table(zone_data, colWidths=[0.8*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("No search zones available for detailed analysis.", self.styles['Normal']))
        
        story.append(Spacer(1, 20))
        return story
    
    def _create_recommendations(self, simulation_data: Dict[str, Any]) -> list:
        """Create recommendations section"""
        story = []
        
        story.append(Paragraph("Search Recommendations", self.styles['SectionHeader']))
        
        recommendations_text = """
        <b>Asset Deployment Recommendations:</b><br/>
        1. Deploy primary search assets to the highest probability zones (>70%)<br/>
        2. Use aircraft for rapid area coverage of medium probability zones<br/>
        3. Position surface vessels in areas with highest debris probability<br/>
        4. Consider wind drift patterns for floating debris search<br/>
        <br/>
        <b>Search Pattern Recommendations:</b><br/>
        • Use expanding square search pattern from zone centers<br/>
        • Prioritize daylight hours for visual search operations<br/>
        • Account for current weather conditions and forecasts<br/>
        • Establish search coordination center for multi-asset operations<br/>
        <br/>
        <b>Continuous Analysis:</b><br/>
        • Update probability zones as new evidence becomes available<br/>
        • Reassess search areas based on negative search results<br/>
        • Monitor weather changes affecting drift calculations<br/>
        """
        
        story.append(Paragraph(recommendations_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_map_section(self, simulation_data: Dict[str, Any]) -> list:
        """Create map visualization section (placeholder)"""
        story = []
        
        story.append(Paragraph("Search Zone Map", self.styles['SectionHeader']))
        
        # Placeholder for map - in production, this would generate an actual map image
        map_text = """
        [Map visualization would be inserted here showing:]<br/>
        • Probability zones color-coded by risk level<br/>
        • Last known aircraft position<br/>
        • Wind vectors and direction<br/>
        • Recommended search patterns<br/>
        • Asset deployment suggestions<br/>
        <br/>
        Map coordinates and zone boundaries are available in the accompanying GeoJSON data.
        """
        
        story.append(Paragraph(map_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        return story

# Async wrapper functions for FastAPI background tasks
async def generate_pdf_report(export_id: str, simulation_data: Dict[str, Any], request: Dict[str, Any]):
    """Async wrapper for PDF report generation"""
    generator = SAR_ReportGenerator()
    try:
        filepath = await generator.generate_pdf_report(export_id, simulation_data, request)
        logger.info(f"PDF report generated successfully: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise

async def generate_csv_export(export_id: str, simulation_data: Dict[str, Any]):
    """Generate CSV export of simulation data"""
    try:
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"SAR_Data_{export_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Extract zone data for CSV
        geojson = simulation_data.get('geojson', {})
        features = geojson.get('features', [])
        
        # Create CSV content
        csv_lines = ['Zone_ID,Probability,Area_km2,Risk_Level,Latitude,Longitude,Perimeter_km']
        
        for i, feature in enumerate(features):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            
            # Calculate centroid for lat/lon
            if geom.get('type') == 'Polygon' and geom.get('coordinates'):
                coords = geom['coordinates'][0]
                if coords:
                    avg_lat = sum(coord[1] for coord in coords) / len(coords)
                    avg_lon = sum(coord[0] for coord in coords) / len(coords)
                else:
                    avg_lat = avg_lon = 0
            else:
                avg_lat = avg_lon = 0
            
            csv_line = f"{i+1},{props.get('probability', 0):.4f},{props.get('area_km2', 0):.2f}," \
                      f"{props.get('risk_level', 'unknown')},{avg_lat:.6f},{avg_lon:.6f}," \
                      f"{props.get('perimeter_km', 0):.2f}"
            csv_lines.append(csv_line)
        
        # Write CSV file
        with open(filepath, 'w', newline='') as f:
            f.write('\n'.join(csv_lines))
        
        logger.info(f"CSV export generated: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"CSV generation failed: {str(e)}")
        raise
