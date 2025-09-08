import os
import boto3
import time
from botocore.exceptions import ClientError
import ProcessLogger

class TextractPdfTextExtractor:
    logger = ProcessLogger.getLogger('Textract')

    def __init__(self, indir, outdir, pages, language, use_cache=True):
        self.outdir = outdir
        
        # Initialize AWS Textract client with environment variables
        self.textract_client = self._initialize_textract_client()
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

    def _initialize_textract_client(self):
        """
        Initialize Textract client using environment variables
        """
        try:
            # Check if we have AWS credentials in environment
            aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            
            if aws_access_key and aws_secret_key:
                self.logger.info(f'Using AWS credentials from environment variables')
                return boto3.client(
                    'textract',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                # Fall back to default credential chain (IAM roles, etc.)
                self.logger.info(f'Using AWS default credential chain')
                return boto3.client('textract', region_name=aws_region)
                
        except Exception as e:
            self.logger.error(f'Failed to initialize Textract client: {e}')
            raise

    def processDocumentWithS3Url(self, s3_url):
        """
        Process entire PDF document using S3 URL directly
        """
        try:
            self.logger.info(f'Processing document: {s3_url}')
            
            # Extract bucket and key from S3 URL
            bucket = self._extract_bucket_from_url(s3_url)
            key = self._extract_key_from_url(s3_url)
            
            # Start document analysis for text + table structure
            response = self.textract_client.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=['TABLES']
            )
            
            job_id = response['JobId']
            self.logger.info(f'Textract job started: {job_id}')
            
            # Wait for job completion
            blocks = self._wait_for_completion(job_id)
            
            # Process extracted data with comprehensive features
            processed_result = self._process_extracted_data(blocks)
            
            # Write output files
            self._write_output_files(processed_result)
            
            return processed_result
                
        except ClientError as e:
            self.logger.error(f'AWS Textract error: {e}')
            raise
        except Exception as e:
            self.logger.error(f'Unexpected error: {e}')
            raise

    def _extract_bucket_from_url(self, url):
        """
        Extract bucket name from S3 URL
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme == 's3':
            return parsed.hostname
        
        if '.s3.' in parsed.hostname and '.amazonaws.com' in parsed.hostname:
            hostname_parts = parsed.hostname.split('.')
            return hostname_parts[0]
        
        if parsed.hostname == 's3.amazonaws.com':
            return parsed.path.split('/')[1]
        
        raise ValueError(f"Invalid S3 URL format: {url}")

    def _extract_key_from_url(self, url):
        """
        Extract key from S3 URL
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme == 's3':
            return parsed.path[1:]  # Remove leading slash
        
        if '.s3.' in parsed.hostname and '.amazonaws.com' in parsed.hostname:
            return parsed.path[1:]  # Remove leading slash
        
        if parsed.hostname == 's3.amazonaws.com':
            return '/'.join(parsed.path.split('/')[2:])  # Skip bucket name
        
        raise ValueError(f"Invalid S3 URL format: {url}")

    def _wait_for_completion(self, job_id, max_wait_time=600):
        """
        Wait for Textract job to complete and return blocks
        Handle pagination to get all blocks
        """
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait_time:
                raise Exception(f'Textract job timed out after {max_wait_time} seconds')
                
            response = self.textract_client.get_document_analysis(JobId=job_id)
            status = response['JobStatus']
            
            if status == 'SUCCEEDED':
                # Collect all blocks, handling pagination
                all_blocks = response.get('Blocks', [])
                next_token = response.get('NextToken')
                
                # Handle pagination
                while next_token:
                    next_response = self.textract_client.get_document_analysis(
                        JobId=job_id,
                        NextToken=next_token
                    )
                    next_blocks = next_response.get('Blocks', [])
                    all_blocks.extend(next_blocks)
                    next_token = next_response.get('NextToken')
                
                self.logger.info(f'Textract analysis completed: {len(all_blocks)} blocks collected')
                return all_blocks
            elif status == 'FAILED':
                raise Exception(f'Textract job failed: {response.get("StatusMessage", "Unknown error")}')
            elif status == 'IN_PROGRESS':
                time.sleep(5)
            else:
                raise Exception(f'Unexpected job status: {status}')

    def _process_extracted_data(self, blocks):
        """
        Comprehensive data processing similar to JavaScript implementation
        """
        start_time = time.time()

        # Separate different block types
        text_blocks = [block for block in blocks if block['BlockType'] == 'LINE']
        table_blocks = [block for block in blocks if block['BlockType'] == 'TABLE']
        form_blocks = [block for block in blocks if block['BlockType'] == 'KEY_VALUE_SET']
        page_blocks = [block for block in blocks if block['BlockType'] == 'PAGE']

        # Process tables with enhanced structure (for single-page documents)
        processed_tables = self._process_tables_enhanced(table_blocks, blocks)

        # Process forms and key-value pairs (for single-page documents)
        processed_forms = self._process_forms_enhanced(form_blocks, blocks)

        # Calculate confidence scores
        confidence = self._calculate_confidence(blocks, threshold=80)

        # Generate statistics
        statistics = {
            'textBlocks': len(text_blocks),
            'tables': len(table_blocks),
            'forms': len(form_blocks),
            'pages': len(page_blocks),
            'totalBlocks': len(blocks),
            'averageConfidence': confidence['average'],
        }

        processing_time = time.time() - start_time

        # Handle single vs multi-page documents
        if len(page_blocks) > 1:
            # Multi-page document - separate by pages
            pages_data = []
            for page_num, page_block in enumerate(page_blocks, 1):
                # Get blocks for this specific page
                page_blocks_data = [block for block in blocks if block.get('Page') == page_num]
                
                # Separate different block types for this page
                page_text_blocks = [block for block in page_blocks_data if block['BlockType'] == 'LINE']
                page_table_blocks = [block for block in page_blocks_data if block['BlockType'] == 'TABLE']
                
                # Process text for this page (including table content)
                page_text = self._process_page_content_complete(page_text_blocks, page_table_blocks, page_blocks_data)
                
                # Calculate confidence for this page
                page_confidence = self._calculate_confidence(page_blocks_data, threshold=80)
                
                # Always add page, even if empty (to maintain page numbering)
                pages_data.append({
                    'page': page_num,
                    'text': page_text,
                    'statistics': {
                        'textBlocks': len(page_text_blocks),
                        'tableBlocks': len(page_table_blocks),
                        'confidence': page_confidence['average'],
                    }
                })
            
            return {
                'pages': pages_data,
                'totalPages': len(page_blocks),
                'overallStatistics': statistics,
                'structuredData': {
                    'tables': processed_tables,
                    'forms': processed_forms,
                },
                'layout': self._generate_layout_map(blocks),
                'confidence': confidence,
                'processingTime': processing_time,
            }
        else:
            # Single page document - process text with layout preservation
            processed_text = self._process_text_with_layout(text_blocks)
            return {
                'text': processed_text,
                'structuredData': {
                    'tables': processed_tables,
                    'forms': processed_forms,
                },
                'layout': self._generate_layout_map(blocks),
                'confidence': confidence,
                'statistics': statistics,
                'processingTime': processing_time,
            }

    def _process_page_content_complete(self, text_blocks, table_blocks, all_page_blocks):
        """
        Process complete page content with proper positioning of text and tables
        """
        # First, identify which LINE blocks belong to tables
        table_line_block_ids = self._get_table_line_block_ids(table_blocks, all_page_blocks)
        
        # Filter out LINE blocks that belong to tables
        non_table_text_blocks = [
            block for block in text_blocks 
            if block['Id'] not in table_line_block_ids
        ]
        
        # Combine text and table blocks for processing
        all_content_blocks = []
        
        # Add non-table text blocks
        for block in non_table_text_blocks:
            all_content_blocks.append({
                'block': block,
                'type': 'text',
                'position': self._get_block_position(block)
            })
        
        # Add table blocks
        for block in table_blocks:
            all_content_blocks.append({
                'block': block,
                'type': 'table',
                'position': self._get_block_position(block)
            })
        
        # Sort all blocks by position with tolerance for same-line detection
        all_content_blocks.sort(key=lambda x: self._get_sort_key_with_tolerance(x['position']))
        
        # Process blocks in order
        content_parts = []
        for item in all_content_blocks:
            if item['type'] == 'text':
                text = item['block'].get('Text', '').strip()
                if text:
                    content_parts.append(text)
            elif item['type'] == 'table':
                # Get table cells
                table_cells = []
                if item['block'].get('Relationships'):
                    for rel in item['block']['Relationships']:
                        if rel['Type'] == 'CHILD':
                            for child_id in rel['Ids']:
                                child_block = next(
                                    (b for b in all_page_blocks if b['Id'] == child_id), 
                                    None
                                )
                                if child_block and child_block['BlockType'] == 'CELL':
                                    table_cells.append(child_block)
                
                if table_cells:
                    table_text = self._process_table_to_text(table_cells, all_page_blocks)
                    if table_text:
                        content_parts.append(table_text)
        
        # Join all content with proper line breaks
        return self.nl2br('\n'.join(content_parts))
    
    def _get_table_line_block_ids(self, table_blocks, all_page_blocks):
        """
        Get IDs of all LINE blocks that belong to tables
        Logic: Find LINE blocks where ALL their WORD children belong to table cells
        """
        # Step 1: Get all WORD IDs that belong to table cells
        table_word_ids = set()
        
        for table_block in table_blocks:
            if table_block.get('Relationships'):
                for rel in table_block['Relationships']:
                    if rel['Type'] == 'CHILD':
                        for child_id in rel['Ids']:
                            child_block = next(
                                (b for b in all_page_blocks if b['Id'] == child_id), 
                                None
                            )
                            if child_block and child_block['BlockType'] == 'CELL':
                                # Get WORD children of this cell
                                if child_block.get('Relationships'):
                                    for cell_rel in child_block['Relationships']:
                                        if cell_rel['Type'] == 'CHILD':
                                            for word_id in cell_rel['Ids']:
                                                word_block = next(
                                                    (b for b in all_page_blocks if b['Id'] == word_id), 
                                                    None
                                                )
                                                if word_block and word_block['BlockType'] == 'WORD':
                                                    table_word_ids.add(word_id)
        
        # Step 2: Find LINE blocks where ALL their WORD children are from table cells
        table_line_block_ids = set()
        
        for line_block in all_page_blocks:
            if line_block['BlockType'] == 'LINE' and line_block.get('Relationships'):
                line_word_ids = set()
                
                # Get all WORD children of this LINE block
                for rel in line_block['Relationships']:
                    if rel['Type'] == 'CHILD':
                        for child_id in rel['Ids']:
                            child_block = next(
                                (b for b in all_page_blocks if b['Id'] == child_id), 
                                None
                            )
                            if child_block and child_block['BlockType'] == 'WORD':
                                line_word_ids.add(child_id)
                
                # If ALL words in this LINE belong to table cells, exclude this LINE
                if line_word_ids and line_word_ids.issubset(table_word_ids):
                    table_line_block_ids.add(line_block['Id'])
        
        return table_line_block_ids
    
    def _get_block_position(self, block):
        """
        Get position of a block for sorting
        """
        geometry = block.get('Geometry', {}).get('BoundingBox', {})
        return {
            'top': geometry.get('Top', 0),
            'left': geometry.get('Left', 0)
        }
    
    def _get_sort_key_with_tolerance(self, position):
        """
        Get sort key with tolerance for same-line detection
        """
        tolerance = 0.03  # 3% tolerance for considering blocks on same line
        
        # Round top position to nearest tolerance to group same-line blocks
        rounded_top = round(position['top'] / tolerance) * tolerance
        
        return (rounded_top, position['left'])
    
    def _sort_blocks_by_position(self, blocks):
        """
        Centralized function to sort blocks by position (top to bottom, left to right)
        """
        return sorted(blocks, key=lambda block: (
            block.get('Geometry', {}).get('BoundingBox', {}).get('Top', 0),
            block.get('Geometry', {}).get('BoundingBox', {}).get('Left', 0)
        ))
    
    def _process_table_to_text(self, table_cells, all_blocks):
        """
        Convert table cells to text format using proper table structure
        """
        if not table_cells:
            return ''
        
        # Build table structure using RowIndex/ColumnIndex
        table_structure = self._build_table_structure(table_cells, all_blocks)
        
        # Convert to text format
        return self._table_structure_to_text(table_structure)
    
    def _build_table_structure(self, table_cells, all_blocks):
        """
        Build proper table structure using Textract table properties
        """
        # Find table dimensions
        max_row = max(cell.get('RowIndex', 0) for cell in table_cells)
        max_col = max(cell.get('ColumnIndex', 0) for cell in table_cells)
        
        # Create table grid
        table_grid = [[None for _ in range(max_col)] for _ in range(max_row)]
        
        # Fill table with cell data
        for cell in table_cells:
            row_idx = cell.get('RowIndex', 1) - 1  # Convert to 0-based
            col_idx = cell.get('ColumnIndex', 1) - 1  # Convert to 0-based
            row_span = cell.get('RowSpan', 1)
            col_span = cell.get('ColumnSpan', 1)
            
            # Get cell text
            cell_text = self._get_cell_text(cell, all_blocks)
            
            # Get cell type (header, footer, etc.)
            cell_type = self._get_cell_type(cell)
            
            # Store cell data
            cell_data = {
                'text': cell_text or '',
                'type': cell_type,
                'row_span': row_span,
                'col_span': col_span
            }
            
            # Fill the cell and its spans
            for r in range(row_idx, min(row_idx + row_span, max_row)):
                for c in range(col_idx, min(col_idx + col_span, max_col)):
                    if table_grid[r][c] is None:  # Don't overwrite existing cells
                        table_grid[r][c] = cell_data
        
        return table_grid
    
    def _get_cell_type(self, cell):
        """
        Get cell type from Textract entity types
        """
        entity_types = cell.get('EntityTypes', [])
        if 'COLUMN_HEADER' in entity_types:
            return 'header'
        elif 'TABLE_TITLE' in entity_types:
            return 'title'
        elif 'TABLE_FOOTER' in entity_types:
            return 'footer'
        elif 'TABLE_SUMMARY' in entity_types:
            return 'summary'
        else:
            return 'data'
    
    def _table_structure_to_text(self, table_grid):
        """
        Convert table structure to text format
        """
        if not table_grid:
            return ''
        
        table_rows = []
        for i, row in enumerate(table_grid):
            row_texts = []
            for j, cell in enumerate(row):
                if cell:
                    row_texts.append(cell['text'])
                else:
                    row_texts.append('')  # Empty cell
            row_text = '|'.join(row_texts)
            table_rows.append(row_text)
        
        final_text = '\n'.join(table_rows)
        
        return final_text

    def _process_text_with_layout(self, text_blocks):
        """
        Enhanced text processing with layout preservation for single-page documents
        """
        if not text_blocks:
            return ''

        # Sort blocks by position (top to bottom, left to right)
        sorted_blocks = self._sort_blocks_by_position(text_blocks)

        # Process each block
        processed_lines = []
        for block in sorted_blocks:
            text = block.get('Text', '').strip()
            if text:
                processed_lines.append(text)

        # Convert newlines to HTML br tags to match structured PDF processing
        return self.nl2br('\n'.join(processed_lines))

    def nl2br(self, s):
        """
        Convert newlines to HTML br tags to match structured PDF processing
        This ensures consistent line break handling across both extraction methods
        """
        return '<br />\n'.join(s.split('\n'))

    def _process_tables_enhanced(self, table_blocks, all_blocks):
        """
        Enhanced table processing
        """
        processed_tables = []
        
        for table_block in table_blocks:
            table_id = table_block['Id']

            # Get all cells that are children of this table
            table_cells = []
            if table_block.get('Relationships'):
                for rel in table_block['Relationships']:
                    if rel['Type'] == 'CHILD':
                        for child_id in rel['Ids']:
                            child_block = next(
                                (b for b in all_blocks if b['Id'] == child_id), 
                                None
                            )
                            if child_block and child_block['BlockType'] == 'CELL':
                                table_cells.append(child_block)

            if not table_cells:
                continue

            # Build proper table structure using Textract properties
            table_structure = self._build_table_structure(table_cells, all_blocks)
            
            # Convert to text format
            table_text = self._table_structure_to_text(table_structure)
            table_rows = table_text.split('\n') if table_text else []

            processed_tables.append({
                'id': table_id,
                'confidence': table_block.get('Confidence', 0),
                'rows': table_rows,
                'cellCount': len(table_cells),
                'rowCount': len(table_structure),
                'structure': table_structure,  # Keep structure for future use
            })

        return processed_tables

    def _process_forms_enhanced(self, form_blocks, all_blocks):
        """
        Enhanced form processing
        """
        key_value_pairs = []

        for block in form_blocks:
            if block.get('EntityTypes') and 'KEY' in block['EntityTypes']:
                key_text = self._get_block_text(block, all_blocks)
                value_block = self._find_value_block(block, all_blocks)
                value_text = self._get_block_text(value_block, all_blocks) if value_block else ''

                if key_text and value_text:
                    key_value_pairs.append({
                        'key': key_text.strip(),
                        'value': value_text.strip(),
                        'confidence': block.get('Confidence', 0),
                        'geometry': block.get('Geometry'),
                    })

        return key_value_pairs

    def _find_value_block(self, key_block, all_blocks):
        """
        Find value block for a key block
        """
        if not key_block.get('Relationships'):
            return None

        value_ids = []
        for rel in key_block['Relationships']:
            if rel['Type'] == 'VALUE':
                value_ids.extend(rel['Ids'])

        for block in all_blocks:
            if (block['BlockType'] == 'KEY_VALUE_SET' and 
                block.get('EntityTypes') and 
                'VALUE' in block['EntityTypes'] and 
                block['Id'] in value_ids):
                return block

        return None

    def _get_block_text(self, block, all_blocks):
        """
        Get text from a block - handles both LINE and WORD blocks
        """
        if not block or not block.get('Relationships'):
            return ''

        child_ids = []
        for rel in block['Relationships']:
            if rel['Type'] == 'CHILD':
                child_ids.extend(rel['Ids'])

        # Look for WORD blocks as children (LINE blocks are children of PAGE, not content blocks)
        text_blocks = [
            b for b in all_blocks 
            if b['BlockType'] == 'WORD' and b['Id'] in child_ids
        ]

        # Sort by position to maintain reading order
        text_blocks = self._sort_blocks_by_position(text_blocks)

        return ' '.join([
            block.get('Text', '') 
            for block in text_blocks 
            if block.get('Text', '').strip()
        ])

    def _get_cell_text(self, cell, all_blocks):
        """
        Get text from a cell - handles both LINE and WORD blocks
        """
        return self._get_block_text(cell, all_blocks)



    def _calculate_confidence(self, blocks, threshold=80):
        """
        Calculate confidence scores
        """
        confidences = [
            block.get('Confidence', 0) 
            for block in blocks 
            if block.get('Confidence', 0) > 0
        ]

        if not confidences:
            return {
                'average': 0,
                'minimum': 0,
                'maximum': 0,
                'lowConfidenceCount': 0,
                'totalBlocks': 0,
                'threshold': threshold,
            }

        average = sum(confidences) / len(confidences)
        low_confidence_blocks = [conf for conf in confidences if conf < threshold]

        return {
            'average': round(average, 2),
            'minimum': min(confidences),
            'maximum': max(confidences),
            'lowConfidenceCount': len(low_confidence_blocks),
            'totalBlocks': len(confidences),
            'threshold': threshold,
        }

    def _generate_layout_map(self, blocks):
        """
        Generate layout map for debugging
        """
        layout_map = []
        for block in blocks:
            geometry = block.get('Geometry', {}).get('BoundingBox')
            layout_item = {
                'id': block['Id'],
                'type': block['BlockType'],
                'text': block.get('Text', ''),
                'confidence': block.get('Confidence', 0),
                'geometry': None
            }
            
            if geometry:
                layout_item['geometry'] = {
                    'left': geometry['Left'],
                    'top': geometry['Top'],
                    'width': geometry['Width'],
                    'height': geometry['Height'],
                }
            
            layout_map.append(layout_item)
        
        return layout_map

    def extractPagesWithS3Url(self, s3_url):
        """
        Extract text from PDF using a single S3 URL - processes ENTIRE document
        """
        try:
            result = self.processDocumentWithS3Url(s3_url)
            self.logger.info(f'Successfully processed: {s3_url}')
            return result
        except Exception as e:
            self.logger.error(f'Failed to process S3 URL: {e}')
            raise

    def _write_output_files(self, processed_result):
        """
        Write output files for single or multi-page documents
        """
        if 'pages' in processed_result:
            # Multi-page document - write separate files for each page
            for page_data in processed_result['pages']:
                page_num = page_data['page']
                page_text = page_data['text']
                outfile = os.path.join(self.outdir, f"{page_num}.txt")
                with open(outfile, 'w', encoding='utf-8') as op:
                    op.write(page_text)
            
            self.logger.info(f'Document processed: {processed_result["totalPages"]} pages, '
                           f'{processed_result["overallStatistics"]["textBlocks"]} text blocks')
        else:
            # Single page document - write single file
            outfile = os.path.join(self.outdir, "1.txt")
            with open(outfile, 'w', encoding='utf-8') as op:
                op.write(processed_result['text'])
            
            self.logger.info(f'Single page document processed: {processed_result["statistics"]["textBlocks"]} text blocks')

    
